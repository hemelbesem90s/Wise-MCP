"""Foreign exchange rate tools for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from wise_mcp.tools.base import BaseTool, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class GetExchangeRateInput(ToolSchema):
    """Input schema for get_exchange_rate tool."""

    source: str = Field(description="3-letter source currency code (e.g. EUR, USD)")
    target: str = Field(description="3-letter target currency code (e.g. ZAR, GBP)")
    time: str | None = Field(
        default=None,
        description="Optional historical timestamp (ISO 8601, e.g. '2026-01-15T12:00:00Z')",
    )


class GetExchangeRateTool(BaseTool):
    """Get live or historical mid-market foreign exchange rates."""

    name = "get_exchange_rate"
    description = (
        "Retrieve live or historical mid-market exchange rates between currency pairs directly from Wise."
    )
    input_schema = GetExchangeRateInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        source = arguments["source"]
        target = arguments["target"]
        time_val = arguments.get("time")

        rates = await client.get_exchange_rates(source, target, time=time_val)
        return {
            "source": source.upper(),
            "target": target.upper(),
            "count": len(rates),
            "rates": [r.model_dump() for r in rates],
        }
