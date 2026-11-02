"""Unit tests for the Wise MCP Server and Triple-Lock dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest
from pydantic import SecretStr

from wise_mcp.biometric_guard import BiometricVerificationDenied
from wise_mcp.config import MCPConfig
from wise_mcp.server import WiseMCPServer, create_server, main
from wise_mcp.tools.constants import READ_TOOL_NAMES, WRITE_TOOL_NAMES


@pytest.fixture
def test_mcp_config(rsa_keypair: tuple[str, str]) -> MCPConfig:
    priv_pem, _ = rsa_keypair
    return MCPConfig(
        api_token=SecretStr("token-test-xyz"),
        api_url="https://api.wise.com",
        profile_id=12345,
        sca_private_key_pem=SecretStr(priv_pem),
        enable_write_tools=False,
        require_biometric=True,
    )


@pytest.mark.asyncio
async def test_server_list_tools_read_only(test_mcp_config: MCPConfig) -> None:
    server = create_server(test_mcp_config)
    res = await server.request_handlers[ListToolsRequest](ListToolsRequest())
    tools = res.root.tools

    names = {t.name for t in tools}
    assert names == set(READ_TOOL_NAMES)
    for write_name in WRITE_TOOL_NAMES:
        assert write_name not in names


@pytest.mark.asyncio
async def test_server_list_tools_write_enabled(test_mcp_config: MCPConfig) -> None:
    test_mcp_config.enable_write_tools = True
    server = create_server(test_mcp_config)
    res = await server.request_handlers[ListToolsRequest](ListToolsRequest())
    tools = {t.name: t for t in res.root.tools}

    for write_name in WRITE_TOOL_NAMES:
        assert write_name in tools
        schema = tools[write_name].inputSchema
        assert "confirm" in schema["properties"]
        assert "confirm" in schema["required"]


@pytest.mark.asyncio
async def test_server_call_read_tool(
    test_mcp_config: MCPConfig, sample_profiles: list[dict[str, Any]]
) -> None:
    server = create_server(test_mcp_config)

    mock_client = AsyncMock()
    mock_client.list_profiles.return_value = [
        MagicMock(model_dump=lambda: p) for p in sample_profiles
    ]

    with patch.object(WiseMCPServer, "get_client") as mock_get_client:
        mock_get_client.return_value.__aenter__.return_value = mock_client
        res = await server.request_handlers[CallToolRequest](
            CallToolRequest(
                params=CallToolRequestParams(name="list_profiles", arguments={})
            )
        )
        assert res.root.isError is not True
        data = json.loads(res.root.content[0].text)
        assert data["count"] == 2


@pytest.mark.asyncio
async def test_server_call_write_tool_when_disabled_fails(
    test_mcp_config: MCPConfig,
) -> None:
    test_mcp_config.enable_write_tools = False
    server = create_server(test_mcp_config)

    res = await server.request_handlers[CallToolRequest](
        CallToolRequest(
            params=CallToolRequestParams(
                name="create_quote",
                arguments={"source_currency": "EUR", "target_currency": "ZAR", "source_amount": 100},
            )
        )
    )
    assert res.root.isError is True
    err = json.loads(res.root.content[0].text)
    assert "Tool disabled by server policy" in err["error"]


@pytest.mark.asyncio
async def test_server_call_write_tool_without_confirm_fails(
    test_mcp_config: MCPConfig,
) -> None:
    test_mcp_config.enable_write_tools = True
    server = create_server(test_mcp_config)

    # When confirm: False is passed
    res = await server.request_handlers[CallToolRequest](
        CallToolRequest(
            params=CallToolRequestParams(
                name="create_quote",
                arguments={
                    "source_currency": "EUR",
                    "target_currency": "ZAR",
                    "source_amount": 100.0,
                    "confirm": False,
                },
            )
        )
    )
    assert res.root.isError is True
    err = json.loads(res.root.content[0].text)
    assert "Explicit write confirmation required" in err["error"]


@pytest.mark.asyncio
async def test_server_call_write_tool_biometric_denied(
    test_mcp_config: MCPConfig,
) -> None:
    test_mcp_config.enable_write_tools = True
    server = create_server(test_mcp_config)

    with patch(
        "wise_mcp.server.verify_user_presence",
        side_effect=BiometricVerificationDenied("User canceled"),
    ):
        res = await server.request_handlers[CallToolRequest](
            CallToolRequest(
                params=CallToolRequestParams(
                    name="create_quote",
                    arguments={
                        "source_currency": "EUR",
                        "target_currency": "ZAR",
                        "source_amount": 100.0,
                        "confirm": True,
                    },
                )
            )
        )
        assert res.root.isError is True
        err = json.loads(res.root.content[0].text)
        assert "Biometric verification denied" in err["error"]


@pytest.mark.asyncio
async def test_server_call_write_tool_success(
    test_mcp_config: MCPConfig, sample_quote: dict[str, Any]
) -> None:
    test_mcp_config.enable_write_tools = True
    server = create_server(test_mcp_config)

    mock_client = AsyncMock()
    mock_client.config.profile_id = 12345
    mock_client.create_quote.return_value = MagicMock(model_dump=lambda: sample_quote)

    with patch.object(WiseMCPServer, "get_client") as mock_get_client, patch(
        "wise_mcp.server.verify_user_presence", return_value=True
    ):
        mock_get_client.return_value.__aenter__.return_value = mock_client
        res = await server.request_handlers[CallToolRequest](
            CallToolRequest(
                params=CallToolRequestParams(
                    name="create_quote",
                    arguments={
                        "source_currency": "EUR",
                        "target_currency": "ZAR",
                        "source_amount": 1000.0,
                        "confirm": True,
                    },
                )
            )
        )
        assert res.root.isError is not True
        data = json.loads(res.root.content[0].text)
        assert data["id"] == "quote-uuid-abc-123"


def test_cli_set_token() -> None:
    with patch("wise_mcp.server.set_keyring_secret") as mock_set, patch(
        "sys.argv", ["wise-mcp", "--set-token", "my-test-token"]
    ):
        main()
        mock_set.assert_called_once_with("wise_mcp", "api_token", "my-test-token")


def test_cli_generate_sca_keys_to_keyring() -> None:
    with patch("wise_mcp.server.set_keyring_secret") as mock_set, patch(
        "sys.argv", ["wise-mcp", "--generate-sca-keys"]
    ):
        main()
        assert mock_set.call_count == 1
        assert mock_set.call_args[0][0] == "wise_mcp"
        assert mock_set.call_args[0][1] == "sca_private_key_pem"


def test_cli_generate_sca_keys_to_file(tmp_path: Path) -> None:
    key_path = str(tmp_path / "keys" / "wise_private.pem")
    with patch("sys.argv", ["wise-mcp", "--generate-sca-keys", key_path]):
        main()
        p = Path(key_path)
        assert p.is_file()
        assert "-----BEGIN PRIVATE KEY-----" in p.read_text()


def test_cli_fix_keychain_acl() -> None:
    with patch(
        "wise_mcp.server.migrate_macos_keychain_acl", return_value=["api_token"]
    ), patch("sys.argv", ["wise-mcp", "--fix-keychain-acl"]):
        main()


def test_cli_test_biometric_success() -> None:
    with patch("wise_mcp.server.verify_user_presence", return_value=True), patch(
        "sys.argv", ["wise-mcp", "--test-biometric"]
    ):
        main()


def test_cli_test_biometric_denied() -> None:
    with patch(
        "wise_mcp.server.verify_user_presence",
        side_effect=BiometricVerificationDenied("User canceled"),
    ), patch("sys.argv", ["wise-mcp", "--test-biometric"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


def test_cli_check_config(test_mcp_config: MCPConfig) -> None:
    with patch("wise_mcp.server.MCPConfig", return_value=test_mcp_config), patch(
        "sys.argv", ["wise-mcp", "--check-config"]
    ):
        main()


@pytest.mark.asyncio
async def test_server_unknown_tool(test_mcp_config: MCPConfig) -> None:
    server = create_server(test_mcp_config)
    res = await server.request_handlers[CallToolRequest](
        CallToolRequest(
            params=CallToolRequestParams(name="non_existent_tool", arguments={})
        )
    )
    assert res.root.isError is True
    assert "Unknown tool" in res.root.content[0].text


@pytest.mark.asyncio
async def test_server_validation_error(test_mcp_config: MCPConfig) -> None:
    server = create_server(test_mcp_config)
    res = await server.request_handlers[CallToolRequest](
        CallToolRequest(
            params=CallToolRequestParams(
                name="get_exchange_rate", arguments={"source": "EUR"}  # missing 'target'
            )
        )
    )
    assert res.root.isError is True
    assert "required property" in res.root.content[0].text


@pytest.mark.asyncio
async def test_server_close_and_lifespan(test_mcp_config: MCPConfig) -> None:
    mcp_srv = WiseMCPServer(test_mcp_config)
    mcp_srv.close()
    await mcp_srv.aclose()


@pytest.mark.asyncio
async def test_server_unexpected_exception(test_mcp_config: MCPConfig) -> None:
    server = create_server(test_mcp_config)
    with patch.object(WiseMCPServer, "get_client", side_effect=RuntimeError("Boom")):
        res = await server.request_handlers[CallToolRequest](
            CallToolRequest(
                params=CallToolRequestParams(name="list_profiles", arguments={})
            )
        )
        assert res.root.isError is True
        assert "Unexpected error" in res.root.content[0].text
