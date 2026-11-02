"""Unit tests for the Wise async HTTP client and PSD2 SCA retry handler."""

from __future__ import annotations

import json
from typing import Any
import httpx
import pytest
from pydantic import SecretStr

from wise.client import WiseClient
from wise.config import WiseConfig
from wise.exceptions import (
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    PaymentError,
    RateLimitError,
    SCARequiredError,
    ValidationError,
    WiseError,
)


@pytest.mark.asyncio
async def test_list_and_get_profiles(
    mock_config: WiseConfig, sample_profiles: list[dict[str, Any]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/profiles":
            return httpx.Response(200, json=sample_profiles)
        if request.url.path == "/v1/profiles/12345":
            return httpx.Response(200, json=sample_profiles[0])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        profiles = await client.list_profiles()
        assert len(profiles) == 2
        assert profiles[0].id == 12345
        assert profiles[0].display_name == "Acme Corp BV"
        assert profiles[1].display_name == "Jane Doe"

        single = await client.get_profile(12345)
        assert single.id == 12345


@pytest.mark.asyncio
async def test_list_and_get_balances(
    mock_config: WiseConfig, sample_balances: list[dict[str, Any]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v4/profiles/12345/balances":
            return httpx.Response(200, json=sample_balances)
        if request.url.path == "/v4/profiles/12345/balances/101":
            return httpx.Response(200, json=sample_balances[0])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        balances = await client.list_balances(12345)
        assert len(balances) == 2
        assert balances[0].currency == "EUR"
        assert balances[0].amount.value == 50000.0

        single = await client.get_balance(12345, 101)
        assert single.id == 101


@pytest.mark.asyncio
async def test_get_exchange_rates(
    mock_config: WiseConfig, sample_rates: list[dict[str, Any]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "source=EUR" in str(request.url)
        assert "target=ZAR" in str(request.url)
        return httpx.Response(200, json=sample_rates)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        rates = await client.get_exchange_rates("EUR", "ZAR")
        assert len(rates) == 1
        assert rates[0].rate == 20.15


@pytest.mark.asyncio
async def test_create_and_get_quote(
    mock_config: WiseConfig, sample_quote: dict[str, Any]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v3/profiles/12345/quotes":
            body = json.loads(request.content.decode("utf-8"))
            assert body["sourceCurrency"] == "EUR"
            assert body["targetCurrency"] == "ZAR"
            return httpx.Response(200, json=sample_quote)
        if request.method == "GET" and "/quotes/quote-uuid-abc-123" in request.url.path:
            return httpx.Response(200, json=sample_quote)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        quote = await client.create_quote(
            12345, "EUR", "ZAR", source_amount=1000.0
        )
        assert quote.id == "quote-uuid-abc-123"
        assert quote.rate == 20.15

        fetched = await client.get_quote(12345, "quote-uuid-abc-123")
        assert fetched.id == "quote-uuid-abc-123"

        # Invalid: both source and target amounts
        with pytest.raises(ValidationError, match="Exactly one of"):
            await client.create_quote(
                12345, "EUR", "ZAR", source_amount=100.0, target_amount=200.0
            )


@pytest.mark.asyncio
async def test_get_balance_statement(
    mock_config: WiseConfig, sample_statement: dict[str, Any]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "statement.json" in request.url.path:
            return httpx.Response(200, json=sample_statement)
        if "statement.csv" in request.url.path:
            return httpx.Response(200, text="Date,Amount,Currency\n2026-01-15,-500,EUR")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        stmt_json = await client.get_balance_statement(
            12345,
            101,
            "EUR",
            "2026-01-01T00:00:00.000Z",
            "2026-01-31T23:59:59.999Z",
            file_format="json",
        )
        assert len(stmt_json["transactions"]) == 1

        stmt_csv = await client.get_balance_statement(
            12345,
            101,
            "EUR",
            "2026-01-01T00:00:00.000Z",
            "2026-01-31T23:59:59.999Z",
            file_format="csv",
        )
        assert "Date,Amount,Currency" in stmt_csv


@pytest.mark.asyncio
async def test_recipients(
    mock_config: WiseConfig, sample_recipients: list[dict[str, Any]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/accounts":
            return httpx.Response(200, json=sample_recipients)
        if request.method == "GET" and request.url.path == "/v1/accounts/5551":
            return httpx.Response(200, json=sample_recipients[0])
        if request.method == "POST" and request.url.path == "/v1/accounts":
            body = json.loads(request.content.decode("utf-8"))
            new_rec = dict(sample_recipients[0])
            new_rec["accountHolderName"] = body["accountHolderName"]
            return httpx.Response(200, json=new_rec)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        recipients = await client.list_recipients()
        assert len(recipients) == 2

        filtered = await client.list_recipients(search="Hetzner")
        assert len(filtered) == 1
        assert filtered[0].id == 5552

        single = await client.get_recipient(5551)
        assert single.id == 5551

        created = await client.create_recipient(
            12345,
            "Cape Engineering Tech (Pty) Ltd",
            "ZAR",
            "south_africa",
            {"accountNumber": "1234567890", "branchCode": "250655"},
        )
        assert created.accountHolderName == "Cape Engineering Tech (Pty) Ltd"


@pytest.mark.asyncio
async def test_transfers_and_funding(
    mock_config: WiseConfig, sample_transfers: list[dict[str, Any]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/transfers":
            return httpx.Response(200, json=sample_transfers)
        if request.method == "GET" and request.url.path == "/v1/transfers/9991":
            return httpx.Response(200, json=sample_transfers[0])
        if request.method == "POST" and request.url.path == "/v1/transfers":
            return httpx.Response(200, json=sample_transfers[0])
        if (
            request.method == "POST"
            and request.url.path == "/v3/profiles/12345/transfers/9991/payments"
        ):
            return httpx.Response(
                200,
                json={"type": "BALANCE", "status": "COMPLETED", "balanceId": 101},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        transfers = await client.list_transfers(12345)
        assert len(transfers) == 1
        assert transfers[0].id == 9991

        single = await client.get_transfer(9991)
        assert single.id == 9991

        staged = await client.stage_transfer(
            5551, "quote-uuid-abc-123", reference="INV-2026-001"
        )
        assert staged.status == "incoming_payment_waiting"

        payment = await client.fund_transfer(12345, 9991, balance_id=101)
        assert payment.status == "COMPLETED"
        assert payment.balanceId == 101


@pytest.mark.asyncio
async def test_sca_403_challenge_signing_and_transparent_retry(
    mock_config: WiseConfig, sample_statement: dict[str, Any]
) -> None:
    """Test that HTTP 403 with x-2fa-approval triggers RSA signature and transparent retry."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt: challenge with 403 and x-2fa-approval OTT
            return httpx.Response(
                403,
                headers={
                    "x-2fa-approval": "ott-challenge-token-999",
                    "x-2fa-approval-result": "REJECTED",
                },
                json={"message": "Two factor authentication required"},
            )
        # Second attempt: check signed headers
        assert request.headers.get("x-2fa-approval") == "ott-challenge-token-999"
        sig = request.headers.get("X-Signature")
        assert sig is not None and len(sig) > 20
        return httpx.Response(200, json=sample_statement)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        data = await client.get_balance_statement(
            12345, 101, "EUR", "2026-01-01T00:00:00Z", "2026-01-31T23:59:59Z"
        )
        assert call_count == 2
        assert len(data["transactions"]) == 1


@pytest.mark.asyncio
async def test_sca_403_without_private_key_raises(
    sample_statement: dict[str, Any]
) -> None:
    """Test that 403 with x-2fa-approval raises SCARequiredError if no key configured."""
    config_no_key = WiseConfig(
        api_token=SecretStr("token-123"),
        api_url="https://api.wise.com",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={
                "x-2fa-approval": "ott-challenge-token-888",
                "x-2fa-approval-result": "REJECTED",
            },
            json={"message": "Two factor authentication required"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(config_no_key, http_client=http)
        with pytest.raises(SCARequiredError, match="Strong Customer Authentication"):
            await client.get_balance_statement(
                12345, 101, "EUR", "2026-01-01T00:00:00Z", "2026-01-31T23:59:59Z"
            )


@pytest.mark.asyncio
async def test_http_error_mappings(mock_config: WiseConfig) -> None:
    async def run_error_check(status: int, exc_type: type[Exception], json_body: dict) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json=json_body)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            client = WiseClient(mock_config, http_client=http)
            with pytest.raises(exc_type):
                await client.list_profiles()

    await run_error_check(401, AuthenticationError, {"message": "Invalid token"})
    await run_error_check(403, ForbiddenError, {"message": "Access denied"})
    await run_error_check(404, NotFoundError, {"message": "Resource not found"})
    await run_error_check(422, ValidationError, {"message": "Unprocessable"})
    await run_error_check(429, RateLimitError, {"message": "Too many requests"})
    await run_error_check(500, WiseError, {"message": "Internal server error"})


@pytest.mark.asyncio
async def test_client_init_variations() -> None:
    client = WiseClient(api_token="direct-token-string", profile_id=99)
    assert client.config.api_token.get_secret_value() == "direct-token-string"
    assert client.config.profile_id == 99
    await client.aclose()

    with pytest.raises(ValueError, match="api_token is required"):
        WiseClient()


@pytest.mark.asyncio
async def test_client_sync_close() -> None:
    client = WiseClient(api_token="direct-token-string")
    client.close()


@pytest.mark.asyncio
async def test_client_empty_and_204_response(mock_config: WiseConfig) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        res = await client.request("DELETE", "/v1/test")
        assert res == {}


@pytest.mark.asyncio
async def test_fund_transfer_payment_error(mock_config: WiseConfig) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "Insufficient balance funds"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = WiseClient(mock_config, http_client=http)
        with pytest.raises(PaymentError, match="Insufficient balance funds"):
            await client.fund_transfer(12345, 9991)
