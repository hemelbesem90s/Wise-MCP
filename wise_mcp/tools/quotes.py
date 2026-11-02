"""Quote tools for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from wise_mcp.tools.base import BaseTool, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class GetQuoteInput(ToolSchema):
    """Input schema for get_quote tool."""

    quote_id: str = Field(description="Unique quote ID or UUID")
    profile_id: int | None = Field(
        default=None,
        description="Profile ID owning the quote (optional if configured in server environment)",
    )


class GetQuoteTool(BaseTool):
    """Inspect an existing FX quote."""

    name = "get_quote"
    description = (
        "Inspect an existing FX quote by ID or UUID. Returns guaranteed exchange rate, "
        "total Wise fee breakdown, and estimated delivery timeline."
    )
    input_schema = GetQuoteInput

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

        quote = await client.get_quote(profile_id, arguments["quote_id"])
        return quote.model_dump()


class CreateQuoteInput(ToolSchema):
    """Input schema for create_quote tool."""

    source_currency: str = Field(description="3-letter source currency to send (e.g. EUR)")
    target_currency: str = Field(description="3-letter target currency to receive (e.g. ZAR)")
    source_amount: float | None = Field(
        default=None,
        gt=0,
        description="Total amount sent in source currency. Exactly one of source_amount or target_amount is required.",
    )
    target_amount: float | None = Field(
        default=None,
        gt=0,
        description="Exact amount recipient receives in target currency. Exactly one of source_amount or target_amount is required.",
    )
    target_account_id: int | None = Field(
        default=None,
        description="Optional recipient account ID to lock destination routing",
    )
    profile_id: int | None = Field(
        default=None,
        description="Profile ID creating the quote (optional if configured in server environment)",
    )


class CreateQuoteTool(BaseTool):
    """Create an authenticated quote locking in exchange rate and fee."""

    name = "create_quote"
    description = (
        "Create an authenticated Wise quote locking in the mid-market foreign exchange rate "
        "and exact transfer fees for 30 minutes. Returns a quoteUuid required for staging transfers."
    )
    input_schema = CreateQuoteInput

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

        quote = await client.create_quote(
            profile_id,
            arguments["source_currency"],
            arguments["target_currency"],
            source_amount=arguments.get("source_amount"),
            target_amount=arguments.get("target_amount"),
            target_account_id=arguments.get("target_account_id"),
        )
        return quote.model_dump()
