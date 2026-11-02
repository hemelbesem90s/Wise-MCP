"""Balance statement tools with SCA signing for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from wise_mcp.tools.base import BaseTool, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class GetBalanceStatementInput(ToolSchema):
    """Input schema for get_balance_statement tool."""

    balance_id: int = Field(description="Unique balance ID to fetch statement for")
    currency: str = Field(description="3-letter currency code of balance (e.g. EUR, ZAR, USD)")
    interval_start: str = Field(
        description="Statement period start in UTC ISO 8601 (e.g. '2026-01-01T00:00:00.000Z')"
    )
    interval_end: str = Field(
        description="Statement period end in UTC ISO 8601 (e.g. '2026-01-31T23:59:59.999Z')"
    )
    format: Literal["json", "csv", "xml", "camt.053", "mt940"] = Field(
        default="json",
        description="Statement export format (default: json)",
    )
    statement_type: Literal["COMPACT", "FLAT"] = Field(
        default="FLAT",
        description="Statement format type: FLAT (itemized fees per line) or COMPACT (single line per payment)",
    )
    profile_id: int | None = Field(
        default=None,
        description="Profile ID owning the balance (optional if configured in server environment)",
    )


class GetBalanceStatementTool(BaseTool):
    """Fetch balance statements with automatic EEA/UK PSD2 SCA cryptographic signing."""

    name = "get_balance_statement"
    description = (
        "Retrieve official Wise multi-currency balance statements with automatic EEA/UK PSD2 Strong "
        "Customer Authentication (SCA) x-2fa-approval cryptographic signing. Returns detailed transactional "
        "activity, opening/closing balances, and fee breakdowns in JSON, CSV, CAMT.053 XML, or MT940 format."
    )
    input_schema = GetBalanceStatementInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        profile_id = arguments.get("profile_id") or client.config.profile_id
        if not profile_id:
            profiles = await client.list_profiles()
            if len(profiles) == 1:
                profile_id = profiles[0].id
            else:
                profile_ids = [p.id for p in profiles]
                raise ValueError(
                    f"profile_id is required. Available profiles: {profile_ids}."
                )

        balance_id = arguments["balance_id"]
        currency = arguments["currency"]
        start = arguments["interval_start"]
        end = arguments["interval_end"]
        file_format = arguments.get("format", "json")
        statement_type = arguments.get("statement_type", "FLAT")

        data = await client.get_balance_statement(
            profile_id,
            balance_id,
            currency,
            start,
            end,
            file_format=file_format,
            statement_type=statement_type,
        )

        if isinstance(data, dict):
            return {
                "profile_id": profile_id,
                "balance_id": balance_id,
                "currency": currency.upper(),
                "format": file_format,
                "statement": data,
            }

        return {
            "profile_id": profile_id,
            "balance_id": balance_id,
            "currency": currency.upper(),
            "format": file_format,
            "content": str(data),
        }
