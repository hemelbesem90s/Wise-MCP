"""Test fixtures and mock helpers for Wise MCP test suite."""

from __future__ import annotations

from typing import Any
import pytest
from pydantic import SecretStr

from wise.config import WiseConfig
from wise.sca import generate_rsa_keypair


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[str, str]:
    """Generate a test RSA-2048 keypair."""
    return generate_rsa_keypair(2048)


@pytest.fixture
def mock_config(rsa_keypair: tuple[str, str]) -> WiseConfig:
    """Standard test WiseConfig."""
    priv_pem, _ = rsa_keypair
    return WiseConfig(
        api_token=SecretStr("test-token-123"),
        api_url="https://api.wise.com",
        profile_id=12345,
        sca_private_key_pem=SecretStr(priv_pem),
    )


@pytest.fixture
def sample_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": 12345,
            "type": "business",
            "details": {
                "name": "Acme Corp BV",
                "registrationNumber": "12345678",
                "companyType": "LIMITED",
            },
        },
        {
            "id": 67890,
            "type": "personal",
            "fullName": "Jane Doe",
            "details": {
                "firstName": "Jane",
                "lastName": "Doe",
            },
        },
    ]


@pytest.fixture
def sample_balances() -> list[dict[str, Any]]:
    return [
        {
            "id": 101,
            "currency": "EUR",
            "amount": {"value": 50000.0, "currency": "EUR"},
            "reservedAmount": {"value": 0.0, "currency": "EUR"},
            "cashAmount": {"value": 50000.0, "currency": "EUR"},
            "totalWorth": {"value": 50000.0, "currency": "EUR"},
            "type": "STANDARD",
            "name": "EUR Balance",
        },
        {
            "id": 102,
            "currency": "ZAR",
            "amount": {"value": 150000.0, "currency": "ZAR"},
            "reservedAmount": {"value": 0.0, "currency": "ZAR"},
            "cashAmount": {"value": 150000.0, "currency": "ZAR"},
            "totalWorth": {"value": 150000.0, "currency": "ZAR"},
            "type": "SAVINGS",
            "name": "ZAR Tax Jar",
        },
    ]


@pytest.fixture
def sample_rates() -> list[dict[str, Any]]:
    return [
        {
            "rate": 20.15,
            "source": "EUR",
            "target": "ZAR",
            "time": "2026-11-02T10:00:00Z",
        }
    ]


@pytest.fixture
def sample_quote() -> dict[str, Any]:
    return {
        "id": "quote-uuid-abc-123",
        "sourceCurrency": "EUR",
        "targetCurrency": "ZAR",
        "sourceAmount": 1000.0,
        "targetAmount": 20050.0,
        "rate": 20.15,
        "createdTime": "2026-11-02T10:00:00Z",
        "rateExpirationTime": "2026-11-02T10:30:00Z",
        "fee": 5.0,
        "feeBreakdown": {"transferwise": 5.0, "payIn": 0.0},
        "deliveryEstimate": "2026-11-02T14:00:00Z",
    }


@pytest.fixture
def sample_recipients() -> list[dict[str, Any]]:
    return [
        {
            "id": 5551,
            "profile": 12345,
            "accountHolderName": "Cape Engineering Tech (Pty) Ltd",
            "currency": "ZAR",
            "country": "ZA",
            "type": "south_africa",
            "details": {
                "accountNumber": "1234567890",
                "branchCode": "250655",
            },
            "ownedByCustomer": False,
            "active": True,
        },
        {
            "id": 5552,
            "profile": 12345,
            "accountHolderName": "Hetzner Online GmbH",
            "currency": "EUR",
            "country": "DE",
            "type": "iban",
            "details": {
                "iban": "DE89370400440532013000",
                "bic": "BYLADEM1100",
            },
            "ownedByCustomer": False,
            "active": True,
        },
    ]


@pytest.fixture
def sample_transfers() -> list[dict[str, Any]]:
    return [
        {
            "id": 9991,
            "profile": 12345,
            "targetAccount": 5551,
            "quoteUuid": "quote-uuid-abc-123",
            "status": "incoming_payment_waiting",
            "reference": "INV-2026-001",
            "rate": 20.15,
            "created": "2026-11-02T10:15:00Z",
            "sourceValue": 1000.0,
            "targetValue": 20050.0,
            "customerTransactionId": "uuid-client-111",
            "details": {"reference": "INV-2026-001"},
        }
    ]


@pytest.fixture
def sample_statement() -> dict[str, Any]:
    return {
        "accountHolder": {"name": "Acme Corp BV"},
        "balance": {"id": 101, "currency": "EUR"},
        "query": {
            "intervalStart": "2026-01-01T00:00:00.000Z",
            "intervalEnd": "2026-01-31T23:59:59.999Z",
        },
        "transactions": [
            {
                "type": "DEBIT",
                "date": "2026-01-15T12:00:00.000Z",
                "amount": {"value": -500.0, "currency": "EUR"},
                "totalFees": {"value": 1.5, "currency": "EUR"},
                "details": {
                    "description": "Supplier payout",
                    "reference": "INV-99",
                },
                "runningBalance": {"value": 49500.0, "currency": "EUR"},
            }
        ],
    }
