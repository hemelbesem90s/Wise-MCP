"""Base tool abstractions and registry for Wise MCP tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from wise.client import WiseClient


class ToolSchema(BaseModel):
    """Schema for tool input parameters."""

    model_config = ConfigDict(extra="forbid")


class PaginatedInput(ToolSchema):
    """Shared pagination constraints."""

    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Number of items to retrieve (1-100)",
    )
    offset: int | None = Field(
        default=None,
        ge=0,
        description="Number of items to skip (0 or greater)",
    )


class BaseTool(ABC):
    """Base class for all Wise MCP tools."""

    name: str
    description: str
    input_schema: type[ToolSchema] = ToolSchema

    @abstractmethod
    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute the tool with the given arguments."""
        pass

    def get_schema(self) -> dict[str, Any]:
        """Get the JSON schema for this tool's input parameters."""
        schema = self.input_schema.model_json_schema()
        schema.pop("title", None)
        return schema


class ToolRegistry:
    """Registry for managing MCP tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())
