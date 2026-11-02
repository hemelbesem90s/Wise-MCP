"""MCP server for Wise multi-currency treasury, SCA signing, and payouts."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import ValidationError

from wise import WiseClient, WiseConfig
from wise.exceptions import WiseError
from wise.sca import generate_rsa_keypair
from wise_mcp.biometric_guard import (
    BiometricHardwareUnavailable,
    BiometricVerificationDenied,
    format_write_prompt,
    verify_user_presence,
)
from wise_mcp.config import (
    MCPConfig,
    migrate_macos_keychain_acl,
    set_keyring_secret,
)
from wise_mcp.tools import (
    DESTRUCTIVE_TOOL_NAMES,
    WRITE_TOOL_NAMES,
    ToolRegistry,
    register_all_tools,
)

logger = logging.getLogger(__name__)

SERVER_INSTRUCTIONS = (
    "This server provides access to Wise multi-currency treasury operations, FX quotes, "
    "balance statements with PSD2 SCA signing, recipient management, and transfer staging. "
    "Read-only tools are enabled by default. Never expose API tokens or private keys. "
    "Before executing any write action (creating quotes, registering recipients, staging "
    "transfers, or funding payouts), explain the exact amounts, currencies, and recipient "
    "details to the user, and obtain explicit confirmation. All write tools require confirm=true "
    "and native hardware biometric presence verification."
)

WRITE_CONFIRMATION_FIELD = "confirm"


def _error_result(payload: dict) -> CallToolResult:
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(payload, default=str, ensure_ascii=False),
            )
        ],
        isError=True,
    )


class WiseMCPServer:
    """MCP server wrapping the Wise SDK."""

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self.registry = ToolRegistry()
        self._client: WiseClient | None = None

        # Register tools
        register_all_tools(self.registry)

        # Build SDK config
        self._sdk_config = WiseConfig(
            api_token=config.api_token,
            api_url=config.api_url,
            profile_id=config.profile_id,
            sca_private_key_path=config.sca_private_key_path,
            sca_private_key_pem=config.sca_private_key_pem,
            allow_custom_api_url=config.allow_custom_api_url,
        )

    def tool_is_enabled(self, name: str) -> bool:
        """Return whether an operator enabled the requested capability."""
        if name in WRITE_TOOL_NAMES:
            return self.config.enable_write_tools
        return True

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[WiseClient]:
        """Get an authenticated Wise client."""
        if self._client is None:
            self._client = WiseClient(self._sdk_config)

        try:
            yield self._client
        except Exception:
            if self._client is not None:
                await self._client.aclose()
                self._client = None
            raise

    async def aclose(self) -> None:
        """Close the underlying client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def close(self) -> None:
        """Synchronous close helper."""
        if self._client is not None:
            self._client.close()
            self._client = None


def create_server(config: MCPConfig | None = None) -> Server:
    """Create and configure the MCP server."""
    if config is None:
        config = MCPConfig()

    mcp_server = WiseMCPServer(config)

    @asynccontextmanager
    async def lifespan(_: Server) -> AsyncIterator[None]:
        try:
            yield None
        finally:
            await mcp_server.aclose()

    server = Server(
        config.server_name,
        version=config.server_version,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=lifespan,
    )

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools respecting operator policy."""
        tools = []
        for tool in mcp_server.registry.list_tools():
            if not mcp_server.tool_is_enabled(tool.name):
                continue
            is_write = tool.name in WRITE_TOOL_NAMES
            input_schema = tool.get_schema()
            if is_write:
                input_schema.setdefault("properties", {})[WRITE_CONFIRMATION_FIELD] = {
                    "type": "boolean",
                    "description": (
                        "Set to true only after the user explicitly reviews and confirms "
                        "this exact action, amounts, currencies, and recipient details."
                    ),
                }
                required = input_schema.setdefault("required", [])
                if WRITE_CONFIRMATION_FIELD not in required:
                    required.append(WRITE_CONFIRMATION_FIELD)

            tools.append(
                Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=input_schema,
                    annotations=ToolAnnotations(
                        readOnlyHint=not is_write,
                        destructiveHint=tool.name in DESTRUCTIVE_TOOL_NAMES,
                        idempotentHint=not is_write,
                        openWorldHint=True,
                    ),
                )
            )
        return tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[TextContent] | CallToolResult:
        """Execute a tool by name with Triple-Lock security enforcement."""
        tool = mcp_server.registry.get(name)
        if tool is None:
            return _error_result({"error": f"Unknown tool: {name}"})

        # Lock 1: Tool Category Policy
        if not mcp_server.tool_is_enabled(name):
            return _error_result(
                {
                    "error": "Tool disabled by server policy",
                    "hint": "The operator must explicitly set WISE_MCP_ENABLE_WRITE_TOOLS=true.",
                }
            )

        execution_arguments = dict(arguments or {})

        # Write Tool Gates
        if name in WRITE_TOOL_NAMES:
            # Lock 2: Explicit Confirmation Parameter
            confirmed = (
                execution_arguments.get(WRITE_CONFIRMATION_FIELD) is True
                or execution_arguments.get("confirm_write") is True
            )
            if not confirmed:
                return _error_result(
                    {
                        "error": "Explicit write confirmation required",
                        "hint": (
                            "Explain the exact financial parameters, amounts, and recipient "
                            "details to the user, then call again with confirm=true."
                        ),
                    }
                )
            execution_arguments.pop(WRITE_CONFIRMATION_FIELD, None)
            execution_arguments.pop("confirm_write", None)

            # Lock 3: Native Hardware Biometric Gate
            if mcp_server.config.require_biometric:
                prompt = format_write_prompt(name, execution_arguments)
                try:
                    verify_user_presence(prompt)
                except (
                    BiometricVerificationDenied,
                    BiometricHardwareUnavailable,
                ) as exc:
                    return _error_result(
                        {
                            "error": "Biometric verification denied",
                            "reason": str(exc),
                            "tool": name,
                        }
                    )

        # Validate Schema
        try:
            validated = tool.input_schema.model_validate(execution_arguments)
            execution_arguments = validated.model_dump(exclude_none=True)
        except ValidationError as exc:
            details = [
                {
                    "field": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors(include_input=False)
            ]
            return _error_result(
                {
                    "error": "Invalid tool arguments",
                    "details": details,
                }
            )

        # Tool Execution
        try:
            async with mcp_server.get_client() as client:
                result = await tool.execute(client, execution_arguments)
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, default=str, ensure_ascii=False),
                    )
                ]
        except WiseError as e:
            return _error_result(
                {
                    "error": str(e),
                    "code": getattr(e, "code", None),
                    "status_code": getattr(e, "status_code", None),
                    "details": getattr(e, "details", None),
                }
            )
        except Exception as e:
            logger.exception("Unexpected error executing tool %s", name)
            return _error_result(
                {
                    "error": f"Unexpected error executing {name}: {e}",
                    "hint": "Check the MCP client logs for details.",
                }
            )

    return server


async def run_server(config: MCPConfig | None = None) -> None:
    """Run the MCP server with stdio transport."""
    server = create_server(config)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """CLI entry point for the Wise MCP server."""
    parser = argparse.ArgumentParser(
        description="Wise Hybrid MCP Server: Multi-currency treasury, PSD2 SCA signing, and payouts."
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration and keyring credentials without connecting to Wise",
    )
    parser.add_argument(
        "--test-biometric",
        action="store_true",
        help="Test native OS biometric verification modal (Touch ID / Windows Hello)",
    )
    parser.add_argument(
        "--fix-keychain-acl",
        action="store_true",
        help="Migrate macOS Keychain items to open application ACL to eliminate repeated password prompts",
    )
    parser.add_argument(
        "--set-token",
        metavar="TOKEN",
        help="Store Wise API Bearer token in OS keyring with trusted ACL",
    )
    parser.add_argument(
        "--generate-sca-keys",
        nargs="?",
        const="",
        metavar="KEY_PATH",
        help=(
            "Generate an RSA-2048 keypair for EEA PSD2 Strong Customer Authentication (SCA). "
            "Outputs the public key to upload in Wise Settings -> API tokens, and stores "
            "the private key in OS keyring (or specified file path)."
        ),
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    args = parser.parse_args()

    if args.set_token:
        set_keyring_secret("wise_mcp", "api_token", args.set_token)
        print("Successfully stored api_token in OS keyring under service 'wise_mcp'.")
        return

    if args.generate_sca_keys is not None:
        priv_pem, pub_pem = generate_rsa_keypair(2048)
        dest_path = args.generate_sca_keys.strip()

        if dest_path:
            p = Path(dest_path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(priv_pem, encoding="utf-8")
            # Set secure permissions on private key file (0600)
            try:
                p.chmod(0o600)
            except OSError:
                pass
            print(f"RSA Private Key successfully written to: {p}")
        else:
            set_keyring_secret("wise_mcp", "sca_private_key_pem", priv_pem)
            print("RSA Private Key securely stored in OS keyring under service 'wise_mcp' (account: sca_private_key_pem).")

        print("\n" + "=" * 70)
        print("PUBLIC KEY FOR WISE API STRONG CUSTOMER AUTHENTICATION (SCA)")
        print("=" * 70)
        print("Copy the public key below and paste it in Wise Business:")
        print("Wise Console -> Settings -> API tokens -> Manage 2FA keys -> Upload Public Key\n")
        print(pub_pem.strip())
        print("=" * 70 + "\n")
        return

    if args.fix_keychain_acl:
        migrated = migrate_macos_keychain_acl("wise_mcp")
        print(f"Migrated Keychain ACL for: {', '.join(migrated) or 'none'}")
        return

    if args.test_biometric:
        prompt = "Wise MCP: Biometric Verification Test"
        try:
            verify_user_presence(prompt)
            print("Biometric verification succeeded.")
            return
        except BiometricVerificationDenied as exc:
            print(f"Biometric verification denied: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
        except BiometricHardwareUnavailable as exc:
            print(f"Biometric hardware unavailable: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        except Exception as exc:
            print(f"Biometric verification error: {exc}", file=sys.stderr)
            raise SystemExit(3) from None

    try:
        config = MCPConfig()
    except ValidationError as exc:
        fields = ", ".join(
            ".".join(str(part) for part in error["loc"]) or "configuration"
            for error in exc.errors(include_url=False, include_input=False)
        )
        print(f"Invalid Wise MCP configuration: {fields}", file=sys.stderr)
        print(
            "Set WISE_MCP_API_TOKEN or run 'wise-mcp --set-token <token>'.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

    if args.check_config:
        mode = "write-enabled" if config.enable_write_tools else "read-only"
        has_sca = bool(config.sca_private_key_pem or config.sca_private_key_path)
        sca_status = "configured" if has_sca else "not configured"
        print(f"Configuration valid ({mode}; SCA signing {sca_status}; credentials redacted).")
        return

    logging.basicConfig(level=getattr(logging, config.log_level), stream=sys.stderr)
    asyncio.run(run_server(config))


if __name__ == "__main__":
    main()
