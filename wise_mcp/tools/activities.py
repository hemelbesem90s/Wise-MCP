"""Activity feed tools for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from wise_mcp.tools.base import BaseTool, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class ListActivitiesInput(ToolSchema):
    """Input schema for list_activities tool."""

    profile_id: int | None = Field(
        default=None,
        description="Profile ID to inspect activities for (optional if default profile is configured)",
    )
    monetary_resource_type: str | None = Field(
        default=None,
        description=(
            "Filter by monetary resource type (e.g. 'CARD_TRANSACTION', "
            "'TRANSFER', 'BALANCE_TRANSACTION')"
        ),
    )
    status: str | None = Field(
        default=None,
        description="Filter by activity status (e.g. 'COMPLETED', 'PENDING', 'CANCELLED')",
    )
    since: str | None = Field(
        default=None,
        description="Filter activities created after this ISO-8601 timestamp (e.g. '2026-10-01T00:00:00.000Z')",
    )
    until: str | None = Field(
        default=None,
        description="Filter activities created before this ISO-8601 timestamp (e.g. '2026-11-16T23:59:59.999Z')",
    )
    size: int | None = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of activity items to return (1-100, default 50)",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Cursor string from previous page response for pagination",
    )


class ListActivitiesTool(BaseTool):
    """Retrieve profile activity feed without requiring PSD2 SCA."""

    name = "list_activities"
    description = (
        "Retrieve profile activity feed (interbalance jar movements, card payments, transfers, cashback, and fees) "
        "without requiring PSD2 SCA. Returns human-readable titles, stripped text, and pagination cursor."
    )
    input_schema = ListActivitiesInput

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

        response = await client.list_activities(
            profile_id,
            monetary_resource_type=arguments.get("monetary_resource_type"),
            status=arguments.get("status"),
            since=arguments.get("since"),
            until=arguments.get("until"),
            size=arguments.get("size") or 50,
            next_cursor=arguments.get("next_cursor"),
        )
        return {
            "profile_id": profile_id,
            "cursor": response.cursor,
            "count": len(response.activities),
            "activities": [a.model_dump() for a in response.activities],
        }
