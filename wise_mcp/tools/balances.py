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
