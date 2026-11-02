"""EEA / UK PSD2 Strong Customer Authentication (SCA) RSA digital signature engine."""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from wise.exceptions import SCARequiredError, ValidationError


def generate_rsa_keypair(key_size: int = 2048) -> tuple[str, str]:
    """Generate an RSA key pair suitable for Wise API 2FA digital signing.

    Args:
        key_size: RSA key size in bits (default: 2048).

    Returns:
        A tuple of (private_key_pem, public_key_pem) as strings.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def load_private_key(pem_data: str | bytes, password: bytes | None = None) -> Any:
    """Load an RSA private key from PEM bytes or string.

    Args:
        pem_data: PEM encoded private key data.
        password: Optional password if key is encrypted.

    Returns:
        RSA private key object.

    Raises:
        ValidationError: If key cannot be loaded or is not an RSA private key.
    """
    raw_bytes = pem_data.encode("utf-8") if isinstance(pem_data, str) else pem_data
    try:
        key = serialization.load_pem_private_key(
            raw_bytes,
            password=password,
        )
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise ValidationError(f"Invalid RSA private key PEM: {exc}") from exc

    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValidationError("Loaded key is not an RSA private key.")
    return key


def sign_one_time_token(
    one_time_token: str,
    private_key_pem: str | bytes,
    password: bytes | None = None,
) -> str:
    """Digitally sign the Wise x-2fa-approval one-time token using RSA-SHA256 with PKCS#1 v1.5 padding.

    Args:
        one_time_token: The OTT string received in the HTTP 403 `x-2fa-approval` response header.
        private_key_pem: The RSA private key in PEM format.
        password: Optional password if the private key is encrypted.

    Returns:
        A Base64-encoded ASCII signature string suitable for the `X-Signature` request header.

    Raises:
        SCARequiredError: If signing fails.
    """
    if not one_time_token or not one_time_token.strip():
        raise SCARequiredError("Cannot sign empty or missing one-time token.")

    try:
        key = load_private_key(private_key_pem, password=password)
        data_to_sign = one_time_token.strip().encode("utf-8")
        signature = key.sign(
            data_to_sign,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("ascii")
    except Exception as exc:
        raise SCARequiredError(f"Failed to sign SCA one-time token: {exc}") from exc
