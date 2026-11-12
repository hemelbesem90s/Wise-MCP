"""Configuration and OS keyring integration for Wise Hybrid MCP Server."""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from wise.config import OFFICIAL_API_HOSTS
from wise.exceptions import HostSecurityError

_KEYRING_CACHE: dict[tuple[str, str], str] = {}


def get_keyring_secret(service_name: str, account: str) -> str | None:
    """Read a credential from the OS keyring without triggering macOS password prompts."""
    import keyring

    # Respect mock in unit tests
    if hasattr(keyring.get_password, "_mock_name") or hasattr(
        keyring.get_password, "assert_called"
    ):
        val = keyring.get_password(service_name, account)
        return val.strip() if isinstance(val, str) and val.strip() else None

    cache_key = (service_name, account)
    if cache_key in _KEYRING_CACHE:
        return _KEYRING_CACHE[cache_key]

    if sys.platform == "darwin" and os.path.exists("/usr/bin/security"):
        proc = subprocess.run(  # nosec B603
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                service_name,
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            secret = proc.stdout.strip()
            # macOS `security find-generic-password -w` hex-encodes multiline values (such as PEM keys)
            if secret.startswith("2d2d2d2d2d"):
                try:
                    secret = bytes.fromhex(secret).decode("utf-8").strip()
                except ValueError:
                    pass
            _KEYRING_CACHE[cache_key] = secret
            return secret
        return None

    val = keyring.get_password(service_name, account)
    if isinstance(val, str) and val.strip():
        secret = val.strip()
        _KEYRING_CACHE[cache_key] = secret
        return secret
    return None


def set_keyring_secret(service_name: str, account: str, secret: str) -> None:
    """Store a credential in OS keyring with open application ACL on macOS."""
    cleaned = secret.strip()
    if not cleaned:
        raise ValueError(f"{account} must not be empty")

    _KEYRING_CACHE[(service_name, account)] = cleaned

    if sys.platform == "darwin" and os.path.exists("/usr/bin/security"):
        # Delete existing item first so partition ACL is cleanly updated
        subprocess.run(  # nosec B603
            [
                "/usr/bin/security",
                "delete-generic-password",
                "-s",
                service_name,
                "-a",
                account,
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        proc = subprocess.run(  # nosec B603
            [
                "/usr/bin/security",
                "add-generic-password",
                "-U",
                "-A",
                "-s",
                service_name,
                "-a",
                account,
                "-w",
                cleaned,
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        if proc.returncode == 0:
            return

    import keyring

    keyring.set_password(service_name, account, cleaned)


def migrate_macos_keychain_acl(
    service_name: str = "wise_mcp",
) -> list[str]:
    """Re-store existing macOS Keychain credentials with -A ACL to eliminate repeated password prompts."""
    import keyring

    migrated: list[str] = []
    for account in ("api_token", "sca_private_key_pem"):
        val = keyring.get_password(service_name, account)
        if val and val.strip():
            set_keyring_secret(service_name, account, val.strip())
            migrated.append(account)
    return migrated


class MCPConfig(BaseSettings):
    """Configuration loaded from environment variables and OS keyring."""

    model_config = SettingsConfigDict(
        env_prefix="WISE_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    # Wise API credentials & settings
    api_token: SecretStr = Field(default_factory=lambda: SecretStr(""))
    api_url: str = "https://api.wise.com"
    profile_id: int | None = None
    sca_private_key_path: Path | None = None
    sca_private_key_pem: SecretStr | None = None
    allow_custom_api_url: bool = False

    # MCP server configuration
    server_name: str = "wise"
    server_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "WARNING"
    enable_write_tools: bool = False
    require_biometric: bool = Field(
        default=True,
        validation_alias="WISE_MCP_REQUIRE_BIOMETRIC",
    )
    biometric_ttl_seconds: int = Field(
        default=300,
        ge=0,
        description="Seconds a successful biometric verification remains valid for subsequent batch write calls (0 = prompt on every call)",
        validation_alias="WISE_MCP_BIOMETRIC_TTL_SECONDS",
    )
    keyring_service_name: str = Field(
        default="wise_mcp",
        validation_alias="WISE_MCP_KEYRING_SERVICE",
    )

    @model_validator(mode="before")
    @classmethod
    def resolve_secrets_from_keyring(cls, data: Any) -> Any:
        d = dict(data) if isinstance(data, dict) else {}
        token = d.get("api_token") or d.get("WISE_MCP_API_TOKEN") or os.environ.get("WISE_MCP_API_TOKEN")
        sca_pem = (
            d.get("sca_private_key_pem")
            or d.get("WISE_MCP_SCA_PRIVATE_KEY_PEM")
            or os.environ.get("WISE_MCP_SCA_PRIVATE_KEY_PEM")
        )

        service_name = str(
            d.get("keyring_service_name")
            or os.environ.get("WISE_MCP_KEYRING_SERVICE")
            or "wise_mcp"
        )

        if token is None or sca_pem is None:
            try:
                if token is None:
                    keyring_token = get_keyring_secret(service_name, "api_token")
                    if keyring_token:
                        d["api_token"] = keyring_token
                if sca_pem is None:
                    keyring_pem = get_keyring_secret(service_name, "sca_private_key_pem")
                    if keyring_pem:
                        d["sca_private_key_pem"] = keyring_pem
            except Exception:  # nosec B110
                pass
        return d

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if not token:
            raise ValueError("api_token must not be empty")
        return SecretStr(token)

    @model_validator(mode="after")
    def validate_security_settings(self) -> Self:
        parsed = urlparse(self.api_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise HostSecurityError("api_url must be an absolute HTTPS URL")
        if parsed.username or parsed.password:
            raise HostSecurityError("api_url must not contain embedded user credentials")

        hostname = parsed.hostname.lower()
        if not self.allow_custom_api_url and hostname not in OFFICIAL_API_HOSTS:
            allowed = ", ".join(OFFICIAL_API_HOSTS)
            raise HostSecurityError(
                f"api_url hostname '{hostname}' is not in the allowed list: {allowed}. "
                "Set WISE_MCP_ALLOW_CUSTOM_API_URL=true only for trusted test endpoints."
            )

        if self.sca_private_key_path is not None:
            resolved_path = self.sca_private_key_path.expanduser().resolve()
            if not resolved_path.is_file():
                raise ValueError(
                    f"sca_private_key_path '{self.sca_private_key_path}' does not exist or is not a file."
                )
            self.sca_private_key_path = resolved_path

        return self
