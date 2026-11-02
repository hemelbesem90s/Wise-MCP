"""Unit tests for Wise PSD2 Strong Customer Authentication (SCA) RSA digital signing."""

from __future__ import annotations

import base64
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from wise.exceptions import SCARequiredError, ValidationError
from wise.sca import generate_rsa_keypair, load_private_key, sign_one_time_token


def test_generate_rsa_keypair() -> None:
    priv_pem, pub_pem = generate_rsa_keypair(2048)
    assert "-----BEGIN PRIVATE KEY-----" in priv_pem
    assert "-----END PRIVATE KEY-----" in priv_pem
    assert "-----BEGIN PUBLIC KEY-----" in pub_pem
    assert "-----END PUBLIC KEY-----" in pub_pem

    # Verify key can be loaded
    key = load_private_key(priv_pem)
    assert key.key_size == 2048


def test_sign_one_time_token_and_verify(rsa_keypair: tuple[str, str]) -> None:
    priv_pem, pub_pem = rsa_keypair
    ott = "d94b049b-7324-4f27-ba0e-3cc515a40b99"

    # Sign the token
    sig_b64 = sign_one_time_token(ott, priv_pem)
    assert isinstance(sig_b64, str)
    raw_sig = base64.b64decode(sig_b64)

    # Verify signature against public key
    public_key = serialization.load_pem_public_key(pub_pem.encode("utf-8"))
    assert isinstance(public_key, rsa.RSAPublicKey)
    public_key.verify(
        raw_sig,
        ott.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_sign_empty_token_raises(rsa_keypair: tuple[str, str]) -> None:
    priv_pem, _ = rsa_keypair
    with pytest.raises(SCARequiredError, match="Cannot sign empty"):
        sign_one_time_token("", priv_pem)


def test_sign_invalid_pem_raises() -> None:
    with pytest.raises(SCARequiredError, match="Failed to sign SCA"):
        sign_one_time_token("test-token", "not-a-valid-pem")


def test_load_private_key_invalid() -> None:
    with pytest.raises(ValidationError, match="Invalid RSA private key"):
        load_private_key("garbage")
