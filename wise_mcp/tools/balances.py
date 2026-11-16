"""Multi-currency balance tools for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from wise_mcp.tools.base import BaseTool, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class ListBalancesInput(ToolSchema):
    """Input schema for list_balances tool."""

    profile_id: int | None = Field(
        default=None,
        description="Profile ID to inspect balances for (optional if default profile is configured)",
    )
    types: list[str] | None = Field(
        default=None,
        description="Filter by balance types (e.g. ['STANDARD', 'SAVINGS']). Defaults to both.",
    )


class ListBalancesTool(BaseTool):
    """List real-time multi-currency account balances and jars."""

    name = "list_balances"
    description = (
        "Retrieve real-time multi-currency account balances and savings jars for a Wise profile. "
        "Returns available cash, reserved amounts, and total net worth per currency."
    )
    input_schema = ListBalancesInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        profile_id = arguments.get("profile_id") or client.config.profile_id
        if not profile_id:
            # If not provided, fetch profiles and auto-select if exactly one profile exists
            profiles = await client.list_profiles()
            if len(profiles) == 1:
                profile_id = profiles[0].id
            else:
                profile_ids = [p.id for p in profiles]
                raise ValueError(
                    f"profile_id is required. Available profiles: {profile_ids}. "
                    "Pass profile_id or configure WISE_MCP_PROFILE_ID."
                )

        types = arguments.get("types")
        balances = await client.list_balances(profile_id, types=types)
        return {
            "profile_id": profile_id,
            "count": len(balances),
            "balances": [b.model_dump() for b in balances],
        }


class MoveBalanceInput(ToolSchema):
    """Input schema for move_balance tool."""

    source_balance_id: int = Field(
        description="Source balance ID (standard balance or savings jar)"
    )
    target_balance_id: int = Field(
        description="Target balance ID (standard balance or savings jar)"
    )
    amount: float | None = Field(
        default=None,
        gt=0,
        description="Monetary amount to move (for same-currency jar movements)",
    )
    currency: str | None = Field(
        default=None,
        description="3-letter currency code (e.g. EUR, ZAR, USD)",
    )
    quote_id: str | int | None = Field(
        default=None,
        description="Locked quote ID/UUID (for cross-currency balance conversions)",
    )
    profile_id: int | None = Field(
        default=None,
        description="Profile ID executing the movement (optional if default profile is configured)",
    )
    idempotency_uuid: str | None = Field(
        default=None,
        description="Client idempotency UUID to prevent duplicate movements",
    )


class MoveBalanceTool(BaseTool):
    """Transfer funds internally between Wise balances and savings jars or convert balance currencies."""

    name = "move_balance"
    description = (
        "Transfer funds internally between Wise balances and savings jars (STANDARD <-> SAVINGS) "
        "or convert balance currencies using a locked quote. Requires confirmation and biometric gate."
    )
    input_schema = MoveBalanceInput

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

        movement = await client.move_balance(
            profile_id,
            source_balance_id=arguments["source_balance_id"],
            target_balance_id=arguments["target_balance_id"],
            amount=arguments.get("amount"),
            currency=arguments.get("currency"),
            quote_id=arguments.get("quote_id"),
            idempotency_uuid=arguments.get("idempotency_uuid"),
        )
        return movement.model_dump()
