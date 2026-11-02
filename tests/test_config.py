"""Unit tests for Wise configuration, host validation, and OS keyring resolution."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from wise.config import WiseConfig
from wise.exceptions import HostSecurityError
from wise_mcp.config import (
    MCPConfig,
    get_keyring_secret,
    migrate_macos_keychain_acl,
    set_keyring_secret,
)


def test_wise_config_valid_hosts() -> None:
    for host in (
        "https://api.wise.com",
        "https://api.transferwise.com",
        "https://api.sandbox.transferwise.tech",
        "https://api.wise-sandbox.com",
    ):
        cfg = WiseConfig(api_token=SecretStr("abc"), api_url=host)
        assert cfg.api_url == host


def test_wise_config_disallowed_host() -> None:
    with pytest.raises(HostSecurityError, match="not in the allowed list"):
        WiseConfig(api_token=SecretStr("abc"), api_url="https://malicious.evil.com")


def test_wise_config_allow_custom_api_url() -> None:
    cfg = WiseConfig(
        api_token=SecretStr("abc"),
        api_url="https://localhost:8443",
        allow_custom_api_url=True,
    )
    assert cfg.api_url == "https://localhost:8443"


def test_wise_config_embedded_credentials_rejected() -> None:
    with pytest.raises(HostSecurityError, match="embedded user credentials"):
        WiseConfig(
            api_token=SecretStr("abc"),
            api_url="https://user:pass@api.wise.com",
        )


def test_wise_config_resolve_sca_key_from_pem(rsa_keypair: tuple[str, str]) -> None:
    priv_pem, _ = rsa_keypair
    cfg = WiseConfig(
        api_token=SecretStr("abc"),
        sca_private_key_pem=SecretStr(priv_pem),
    )
    assert cfg.resolve_sca_private_key() == priv_pem.strip()


def test_wise_config_resolve_sca_key_from_path(tmp_path: Path, rsa_keypair: tuple[str, str]) -> None:
    priv_pem, _ = rsa_keypair
    pem_file = tmp_path / "private.pem"
    pem_file.write_text(priv_pem)

    cfg = WiseConfig(
        api_token=SecretStr("abc"),
        sca_private_key_path=pem_file,
    )
    assert cfg.resolve_sca_private_key() == priv_pem.strip()


def test_keyring_get_and_set() -> None:
    with patch("keyring.get_password", return_value="test-secret") as mock_get:
        val = get_keyring_secret("wise_mcp", "api_token")
        assert val == "test-secret"
        mock_get.assert_called_once_with("wise_mcp", "api_token")

    with patch("keyring.set_password"), patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0)
        set_keyring_secret("wise_mcp", "api_token", "new-secret")


def test_migrate_macos_keychain_acl() -> None:
    with patch("keyring.get_password", side_effect=lambda s, a: f"val-{a}"), patch(
        "wise_mcp.config.set_keyring_secret"
    ) as mock_set:
        migrated = migrate_macos_keychain_acl("wise_mcp")
        assert "api_token" in migrated
        assert "sca_private_key_pem" in migrated
        assert mock_set.call_count == 2


def test_mcp_config_keyring_fallback() -> None:
    with patch(
        "wise_mcp.config.get_keyring_secret",
        side_effect=lambda s, a: "keyring-token" if a == "api_token" else "keyring-pem",
    ):
        with patch.dict(os.environ, {}, clear=True):
            cfg = MCPConfig()
            assert cfg.api_token.get_secret_value() == "keyring-token"
            assert cfg.sca_private_key_pem is not None
            assert cfg.sca_private_key_pem.get_secret_value() == "keyring-pem"
