"""MCP tools for Wise operations."""

from wise_mcp.tools.balances import ListBalancesTool
from wise_mcp.tools.base import BaseTool, ToolRegistry
from wise_mcp.tools.constants import (
    DESTRUCTIVE_TOOL_NAMES,
    READ_TOOL_NAMES,
    WRITE_TOOL_NAMES,
)
from wise_mcp.tools.profiles import ListProfilesTool
from wise_mcp.tools.quotes import CreateQuoteTool, GetQuoteTool
from wise_mcp.tools.rates import GetExchangeRateTool
from wise_mcp.tools.recipients import CreateRecipientTool, ListRecipientsTool
from wise_mcp.tools.statements import GetBalanceStatementTool
from wise_mcp.tools.transfers import (
    CancelTransferTool,
    FundTransferTool,
    GetTransferTool,
    ListTransfersTool,
    StageTransferTool,
)


def register_all_tools(registry: ToolRegistry) -> None:
    """Register all available tools with the registry."""
    # Read Tools (8 tools)
    registry.register(ListProfilesTool())
    registry.register(ListBalancesTool())
    registry.register(GetExchangeRateTool())
    registry.register(GetQuoteTool())
    registry.register(GetBalanceStatementTool())
    registry.register(ListRecipientsTool())
    registry.register(ListTransfersTool())
    registry.register(GetTransferTool())

    # Write Tools (5 tools)
    registry.register(CreateQuoteTool())
    registry.register(CreateRecipientTool())
    registry.register(StageTransferTool())
    registry.register(CancelTransferTool())
    registry.register(FundTransferTool())


__all__ = [
    "BaseTool",
    "CancelTransferTool",
    "CreateQuoteTool",
    "CreateRecipientTool",
    "DESTRUCTIVE_TOOL_NAMES",
    "FundTransferTool",
    "GetBalanceStatementTool",
    "GetExchangeRateTool",
    "GetQuoteTool",
    "GetTransferTool",
    "ListBalancesTool",
    "ListProfilesTool",
    "ListRecipientsTool",
    "ListTransfersTool",
    "READ_TOOL_NAMES",
    "StageTransferTool",
    "ToolRegistry",
    "WRITE_TOOL_NAMES",
    "register_all_tools",
]
