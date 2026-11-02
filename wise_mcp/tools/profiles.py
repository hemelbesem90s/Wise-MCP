"""Profile tools for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from wise_mcp.tools.base import BaseTool, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class ListProfilesInput(ToolSchema):
    """Input schema for list_profiles tool."""


class ListProfilesTool(BaseTool):
    """List personal and business Wise profiles."""

    name = "list_profiles"
    description = (
        "List all personal and business profiles associated with the Wise API token. "
        "Returns profile IDs, types, and business details needed for subsequent operations."
    )
    input_schema = ListProfilesInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        profiles = await client.list_profiles()
        return {
            "count": len(profiles),
            "profiles": [p.model_dump() for p in profiles],
        }
