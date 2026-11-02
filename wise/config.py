"""Configuration and security validation for the Wise SDK."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from typing_extensions import Self

from wise.exceptions import HostSecurityError

OFFICIAL_API_HOSTS = (
    "api.wise.com",
    "api.transferwise.com",
    "api.sandbox.transferwise.tech",
    "api.wise-sandbox.com",
)


class WiseConfig(BaseModel):
    """Configuration settings for the Wise SDK client."""

    api_token: SecretStr = Field(description="Wise API Bearer token")
    api_url: str = Field(
        default="https://api.wise.com",
        description="Base URL for the Wise API",
    )
    profile_id: int | None = Field(
        default=None,
        description="Default Wise personal or business profile ID",
    )
    sca_private_key_pem: SecretStr | None = Field(
        default=None,
        description="RSA-2048 private key in PEM format for SCA digital signing",
    )
    sca_private_key_path: Path | None = Field(
        default=None,
        description="Path to local RSA private key PEM file",
    )
    allow_custom_api_url: bool = Field(
        default=False,
        description="Whether to permit non-official API hostnames (strictly for local test mocks)",
    )
    timeout: float = Field(
        default=30.0,
        description="HTTP request timeout in seconds",
    )

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if not token:
            raise ValueError("api_token must not be empty")
        return SecretStr(token)

    @model_validator(mode="after")
    def validate_api_url(self) -> Self:
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
                "Set allow_custom_api_url=True only when using a trusted test mock endpoint."
            )

        if self.sca_private_key_path is not None:
            resolved_path = self.sca_private_key_path.expanduser().resolve()
            if not resolved_path.is_file():
                raise ValueError(
                    f"sca_private_key_path '{self.sca_private_key_path}' does not exist or is not a file."
                )
            self.sca_private_key_path = resolved_path

        return self

    def resolve_sca_private_key(self) -> str | None:
        """Resolve the RSA private key PEM from direct configuration or file path."""
        if self.sca_private_key_pem is not None:
            val = self.sca_private_key_pem.get_secret_value().strip()
            if val:
                return val

        if self.sca_private_key_path is not None and self.sca_private_key_path.is_file():
            try:
                content = self.sca_private_key_path.read_text(encoding="utf-8").strip()
                if content:
                    return content
            except OSError:
                return None

        # Fallback to env var if present
        env_pem = os.environ.get("WISE_MCP_SCA_PRIVATE_KEY_PEM")
        if env_pem and env_pem.strip():
            return env_pem.strip()

        return None
