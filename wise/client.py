"""Async REST API client for Wise with EEA PSD2 SCA digital signature support."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import SecretStr

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
from wise.models.balance import Balance
from wise.models.payment import PaymentResponse
from wise.models.profile import Profile
from wise.models.quote import Quote
from wise.models.rate import ExchangeRate
from wise.models.recipient import Recipient
from wise.models.statement import BalanceStatement
from wise.models.transfer import Transfer
from wise.sca import sign_one_time_token

logger = logging.getLogger(__name__)


class WiseClient:
    """Async client for interacting with the Wise Platform API.

    Features:
    - Native async requests via httpx.AsyncClient.
    - Automatic EEA PSD2 Strong Customer Authentication (SCA) 403 challenge interception:
      signs the `x-2fa-approval` one-time token using the client's RSA private key and retries transparently.
    - Strict host validation and Bearer token lifecycle.
    """

    def __init__(
        self,
        config: WiseConfig | None = None,
        *,
        api_token: str | SecretStr | None = None,
        api_url: str | None = None,
        profile_id: int | None = None,
        sca_private_key_pem: str | SecretStr | None = None,
        allow_custom_api_url: bool = False,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            if api_token is None:
                raise ValueError("api_token is required when config is not provided")
            secret_token = (
                api_token if isinstance(api_token, SecretStr) else SecretStr(api_token)
            )
            secret_pem = (
                sca_private_key_pem
                if isinstance(sca_private_key_pem, SecretStr) or sca_private_key_pem is None
                else SecretStr(sca_private_key_pem)
            )
            self.config = WiseConfig(
                api_token=secret_token,
                api_url=api_url or "https://api.wise.com",
                profile_id=profile_id,
                sca_private_key_pem=secret_pem,
                allow_custom_api_url=allow_custom_api_url,
                timeout=timeout,
            )

        self._http = http_client or httpx.AsyncClient(
            timeout=self.config.timeout,
            headers={
                "Authorization": f"Bearer {self.config.api_token.get_secret_value()}",
                "User-Agent": "wise-mcp/0.1.0 (Python)",
            },
        )
        self._owns_http_client = http_client is None

    async def __aenter__(self) -> WiseClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_http_client and not self._http.is_closed:
            await self._http.aclose()

    def close(self) -> None:
        """Synchronous wrapper to close the client."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.aclose())
            else:
                loop.run_until_complete(self.aclose())
        except RuntimeError:
            asyncio.run(self.aclose())

    def _resolve_url(self, path: str) -> str:
        base = self.config.api_url.rstrip("/") + "/"
        clean_path = path.lstrip("/")
        return urljoin(base, clean_path)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        expect_raw: bool = False,
        sign_sca_on_403: bool = True,
    ) -> Any:
        """Execute an HTTP request with automatic SCA interception and error mapping."""
        url = self._resolve_url(path)
        req_headers = dict(headers or {})
        if json is not None and "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"

        response = await self._http.request(
            method=method,
            url=url,
            params=params,
            json=json,
            headers=req_headers,
        )

        # Handle EEA PSD2 Strong Customer Authentication (SCA) 403 Challenge
        if response.status_code == 403 and sign_sca_on_403:
            one_time_token = response.headers.get("x-2fa-approval")
            if one_time_token:
                logger.info(
                    "SCA 2FA challenge detected (x-2fa-approval). Initiating RSA digital signing."
                )
                private_key_pem = self.config.resolve_sca_private_key()
                if not private_key_pem:
                    approval_result = response.headers.get("x-2fa-approval-result")
                    raise SCARequiredError(
                        "Strong Customer Authentication (SCA) required by Wise ('x-2fa-approval'), "
                        "but no RSA private key is configured. Run 'wise-mcp --generate-sca-keys' "
                        "to generate a keypair and upload the public key to Wise Settings -> API tokens.",
                        one_time_token=one_time_token,
                        approval_result=approval_result,
                    )

                # Sign one-time token with RSA private key
                signature = sign_one_time_token(one_time_token, private_key_pem)

                # Retry request with signed challenge headers
                retry_headers = dict(req_headers)
                retry_headers["x-2fa-approval"] = one_time_token
                retry_headers["X-Signature"] = signature

                logger.debug("Retrying request with x-2fa-approval and X-Signature headers.")
                response = await self._http.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=retry_headers,
                )

        # Process response status
        if 200 <= response.status_code < 300:
            if expect_raw:
                return response.text
            if response.status_code == 204 or not response.content:
                return {}
            try:
                return response.json()
            except Exception:
                return response.text

        # Error response handling
        status_code = response.status_code
        error_details: Any = None
        error_message = f"Wise API error (HTTP {status_code})"
        try:
            error_details = response.json()
            if isinstance(error_details, dict):
                error_message = (
                    error_details.get("error_description")
                    or error_details.get("message")
                    or error_details.get("error")
                    or (
                        error_details.get("errors")
                        and str(error_details.get("errors"))
                    )
                    or error_message
                )
        except Exception:
            text = response.text.strip()
            if text:
                error_message = f"{error_message}: {text[:200]}"

        if status_code == 401:
            raise AuthenticationError(
                error_message, status_code=status_code, details=error_details
            )
        if status_code == 403:
            ott = response.headers.get("x-2fa-approval")
            if ott:
                raise SCARequiredError(
                    error_message,
                    one_time_token=ott,
                    approval_result=response.headers.get("x-2fa-approval-result"),
                    details=error_details,
                )
            raise ForbiddenError(
                error_message, status_code=status_code, details=error_details
            )
        if status_code == 404:
            raise NotFoundError(
                error_message, status_code=status_code, details=error_details
            )
        if status_code in (400, 422):
            raise ValidationError(
                error_message, status_code=status_code, details=error_details
            )
        if status_code == 429:
            raise RateLimitError(
                error_message, status_code=status_code, details=error_details
            )

        raise WiseError(
            error_message, status_code=status_code, details=error_details
        )

    # -------------------------------------------------------------------------
    # Profiles API
    # -------------------------------------------------------------------------
    async def list_profiles(self) -> list[Profile]:
        """List personal and business Wise profiles associated with the API token."""
        data = await self.request("GET", "/v1/profiles")
        if not isinstance(data, list):
            data = [data] if data else []
        return [Profile.model_validate(item) for item in data]

    async def get_profile(self, profile_id: int) -> Profile:
        """Get details for a specific Wise profile."""
        data = await self.request("GET", f"/v1/profiles/{profile_id}")
        return Profile.model_validate(data)

    # -------------------------------------------------------------------------
    # Balances API
    # -------------------------------------------------------------------------
    async def list_balances(
        self, profile_id: int, types: list[str] | None = None
    ) -> list[Balance]:
        """Retrieve real-time multi-currency account balances (STANDARD and SAVINGS/Jars)."""
        params = {}
        if types:
            params["types"] = ",".join(types)
        else:
            params["types"] = "STANDARD,SAVINGS"

        data = await self.request(
            "GET", f"/v4/profiles/{profile_id}/balances", params=params
        )
        if not isinstance(data, list):
            data = [data] if data else []
        return [Balance.model_validate(item) for item in data]

    async def get_balance(self, profile_id: int, balance_id: int) -> Balance:
        """Get details for a specific currency balance."""
        data = await self.request(
            "GET", f"/v4/profiles/{profile_id}/balances/{balance_id}"
        )
        return Balance.model_validate(data)

    # -------------------------------------------------------------------------
    # Exchange Rates API
    # -------------------------------------------------------------------------
    async def get_exchange_rates(
        self, source: str, target: str, time: str | None = None
    ) -> list[ExchangeRate]:
        """Retrieve live or historical mid-market exchange rates between currency pairs."""
        params: dict[str, Any] = {
            "source": source.upper(),
            "target": target.upper(),
        }
        if time:
            params["time"] = time

        data = await self.request("GET", "/v1/rates", params=params)
        if not isinstance(data, list):
            data = [data] if data else []
        return [ExchangeRate.model_validate(item) for item in data]

    # -------------------------------------------------------------------------
    # Quotes API
    # -------------------------------------------------------------------------
    async def create_quote(
        self,
        profile_id: int,
        source_currency: str,
        target_currency: str,
        *,
        source_amount: float | None = None,
        target_amount: float | None = None,
        target_account_id: int | None = None,
    ) -> Quote:
        """Create an authenticated quote locking in the FX rate and exact Wise fee."""
        if (source_amount is None and target_amount is None) or (
            source_amount is not None and target_amount is not None
        ):
            raise ValidationError(
                "Exactly one of 'source_amount' or 'target_amount' must be specified."
            )

        payload: dict[str, Any] = {
            "sourceCurrency": source_currency.upper(),
            "targetCurrency": target_currency.upper(),
        }
        if source_amount is not None:
            payload["sourceAmount"] = source_amount
            payload["targetAmount"] = None
        else:
            payload["sourceAmount"] = None
            payload["targetAmount"] = target_amount

        if target_account_id is not None:
            payload["targetAccount"] = target_account_id

        data = await self.request(
            "POST", f"/v3/profiles/{profile_id}/quotes", json=payload
        )
        return Quote.model_validate(data)

    async def get_quote(self, profile_id: int, quote_id: str | int) -> Quote:
        """Inspect an existing FX quote by ID or UUID."""
        data = await self.request(
            "GET", f"/v3/profiles/{profile_id}/quotes/{quote_id}"
        )
        return Quote.model_validate(data)

    # -------------------------------------------------------------------------
    # Balance Statements API
    # -------------------------------------------------------------------------
    async def get_balance_statement(
        self,
        profile_id: int,
        balance_id: int,
        currency: str,
        interval_start: str,
        interval_end: str,
        *,
        file_format: str = "json",
        statement_type: str = "FLAT",
    ) -> Any:
        """Fetch balance statement with automatic EEA/UK PSD2 Strong Customer Authentication (SCA) signing."""
        clean_ext = file_format.lower().lstrip(".")
        # Map friendly format names to extension
        if clean_ext in ("camt.053", "camt053"):
            ext = "xml"
        else:
            ext = clean_ext

        path = f"/v1/profiles/{profile_id}/balance-statements/{balance_id}/statement.{ext}"
        params = {
            "currency": currency.upper(),
            "intervalStart": interval_start,
            "intervalEnd": interval_end,
            "type": statement_type.upper(),
        }

        expect_raw = ext != "json"
        data = await self.request(
            "GET", path, params=params, expect_raw=expect_raw, sign_sca_on_403=True
        )
        if ext == "json" and isinstance(data, dict):
            try:
                return BalanceStatement.model_validate(data).model_dump()
            except Exception:
                return data
        return data

    # -------------------------------------------------------------------------
    # Recipients API
    # -------------------------------------------------------------------------
    async def list_recipients(
        self,
        profile_id: int | None = None,
        *,
        currency: str | None = None,
        search: str | None = None,
    ) -> list[Recipient]:
        """List and search recipient bank accounts."""
        params: dict[str, Any] = {}
        target_profile = profile_id or self.config.profile_id
        if target_profile:
            params["profile"] = target_profile
        if currency:
            params["currency"] = currency.upper()

        data = await self.request("GET", "/v1/accounts", params=params)
        if not isinstance(data, list):
            data = [data] if data else []

        recipients = [Recipient.model_validate(item) for item in data]
        if search:
            q = search.lower().strip()
            recipients = [
                r
                for r in recipients
                if q in r.accountHolderName.lower()
                or (r.currency and q in r.currency.lower())
                or (r.details and any(q in str(v).lower() for v in r.details.values()))
            ]
        return recipients

    async def get_recipient(self, account_id: int) -> Recipient:
        """Get details for a specific recipient bank account."""
        data = await self.request("GET", f"/v1/accounts/{account_id}")
        return Recipient.model_validate(data)

    async def create_recipient(
        self,
        profile_id: int,
        account_holder_name: str,
        currency: str,
        account_type: str,
        details: dict[str, Any],
        *,
        owned_by_customer: bool = False,
    ) -> Recipient:
        """Register a new beneficiary recipient bank account."""
        payload = {
            "profile": profile_id,
            "accountHolderName": account_holder_name.strip(),
            "currency": currency.upper(),
            "type": account_type.lower(),
            "details": details,
            "ownedByCustomer": owned_by_customer,
        }
        data = await self.request("POST", "/v1/accounts", json=payload)
        return Recipient.model_validate(data)

    # -------------------------------------------------------------------------
    # Transfers API
    # -------------------------------------------------------------------------
    async def list_transfers(
        self,
        profile_id: int,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        source_currency: str | None = None,
        target_currency: str | None = None,
    ) -> list[Transfer]:
        """List recent transfers and their status."""
        params: dict[str, Any] = {
            "profile": profile_id,
            "limit": min(max(1, limit), 100),
            "offset": max(0, offset),
        }
        if status:
            params["status"] = status
        if source_currency:
            params["sourceCurrency"] = source_currency.upper()
        if target_currency:
            params["targetCurrency"] = target_currency.upper()

        data = await self.request("GET", "/v1/transfers", params=params)
        if not isinstance(data, list):
            data = [data] if data else []
        return [Transfer.model_validate(item) for item in data]

    async def get_transfer(self, transfer_id: int) -> Transfer:
        """Retrieve transfer details and fee/FX metadata for accounting reconciliation."""
        data = await self.request("GET", f"/v1/transfers/{transfer_id}")
        return Transfer.model_validate(data)

    async def stage_transfer(
        self,
        target_account_id: int,
        quote_uuid: str,
        reference: str,
        *,
        customer_transaction_id: str | None = None,
        transfer_purpose: str | None = None,
        source_of_funds: str | None = None,
    ) -> Transfer:
        """Create/stage an unfunded transfer in Wise with reference and idempotency UUID."""
        details: dict[str, Any] = {"reference": reference.strip()}
        if transfer_purpose:
            details["transferPurpose"] = transfer_purpose
        if source_of_funds:
            details["sourceOfFunds"] = source_of_funds

        payload: dict[str, Any] = {
            "targetAccount": target_account_id,
            "quoteUuid": quote_uuid,
            "customerTransactionId": customer_transaction_id or str(uuid.uuid4()),
            "details": details,
        }
        data = await self.request("POST", "/v1/transfers", json=payload)
        return Transfer.model_validate(data)

    async def fund_transfer(
        self,
        profile_id: int,
        transfer_id: int,
        *,
        balance_id: int | None = None,
    ) -> PaymentResponse:
        """Fund a staged transfer from a Wise multi-currency account balance."""
        payload: dict[str, Any] = {"type": "BALANCE"}
        if balance_id is not None:
            payload["balanceId"] = balance_id

        path = f"/v3/profiles/{profile_id}/transfers/{transfer_id}/payments"
        try:
            data = await self.request("POST", path, json=payload, sign_sca_on_403=True)
            return PaymentResponse.model_validate(data)
        except WiseError as exc:
            raise PaymentError(
                f"Failed to fund transfer #{transfer_id}: {exc}",
                status_code=exc.status_code,
                details=exc.details,
            ) from exc
