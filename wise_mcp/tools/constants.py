"""Constants and tool categorization for Wise MCP."""

from __future__ import annotations

# Read-only tools enabled by default
READ_TOOL_NAMES: tuple[str, ...] = (
    "list_profiles",
    "list_balances",
    "get_exchange_rate",
    "get_quote",
    "get_balance_statement",
    "list_recipients",
    "list_transfers",
    "get_transfer",
)

# Write tools requiring WISE_MCP_ENABLE_WRITE_TOOLS=true + confirm: true + biometric gate
WRITE_TOOL_NAMES: tuple[str, ...] = (
    "create_quote",
    "create_recipient",
    "stage_transfer",
    "fund_transfer",
)

# High-risk financial operations
DESTRUCTIVE_TOOL_NAMES: tuple[str, ...] = (
    "fund_transfer",
)
