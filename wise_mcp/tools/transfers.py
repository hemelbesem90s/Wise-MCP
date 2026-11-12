"""Transfer and payout tools for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from wise_mcp.tools.base import BaseTool, PaginatedInput, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class ListTransfersInput(PaginatedInput):
    """Input schema for list_transfers tool."""

    status: str | None = Field(
        default=None,
        description=(
            "Filter transfers by lifecycle status (e.g. 'incoming_payment_waiting', "
            "'processing', 'funds_converted', 'outgoing_payment_sent', 'cancelled')"
        ),
    )
    source_currency: str | None = Field(
        default=None,
        description="Filter by 3-letter source currency",
    )
    target_currency: str | None = Field(
        default=None,
        description="Filter by 3-letter target currency",
    )
    profile_id: int | None = Field(
        default=None,
        description="Profile ID owning the transfers (optional if configured in server environment)",
    )


class ListTransfersTool(BaseTool):
    """List recent transfers and their execution status."""

    name = "list_transfers"
    description = (
        "List recent Wise payment transfers and inspect their lifecycle status "
        "(incoming_payment_waiting, processing, funds_converted, outgoing_payment_sent, cancelled)."
    )
    input_schema = ListTransfersInput

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

        transfers = await client.list_transfers(
            profile_id,
            status=arguments.get("status"),
            limit=arguments.get("limit") or 20,
            offset=arguments.get("offset") or 0,
            source_currency=arguments.get("source_currency"),
            target_currency=arguments.get("target_currency"),
        )
        return {
            "profile_id": profile_id,
            "count": len(transfers),
            "transfers": [t.model_dump() for t in transfers],
        }


class GetTransferInput(ToolSchema):
    """Input schema for get_transfer tool."""

    transfer_id: int = Field(description="Unique transfer ID")


class GetTransferTool(BaseTool):
    """Retrieve transfer details and fee/FX metadata for accounting reconciliation."""

    name = "get_transfer"
    description = (
        "Retrieve comprehensive transfer details, exchange rate, fee breakdown, "
        "and timestamps for financial accounting and invoice reconciliation."
    )
    input_schema = GetTransferInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        transfer = await client.get_transfer(arguments["transfer_id"])
        return transfer.model_dump()


class StageTransferInput(ToolSchema):
    """Input schema for stage_transfer tool."""

    target_account_id: int = Field(
        description="Recipient account ID to receive funds"
    )
    quote_uuid: str = Field(
        description="Locked quote UUID created via create_quote"
    )
    reference: str = Field(
        description="Payment reference text appearing on recipient bank statement (e.g. invoice number)"
    )
    customer_transaction_id: str | None = Field(
        default=None,
        description="Client idempotency UUID to prevent duplicate payments. Generated automatically if omitted.",
    )
    transfer_purpose: str | None = Field(
        default=None,
        description="Optional regulatory payment purpose (e.g. 'verification.transfers.purpose.pay.bills')",
    )
    source_of_funds: str | None = Field(
        default=None,
        description="Optional source of funds description",
    )


class StageTransferTool(BaseTool):
    """Create and queue an unfunded transfer in Wise."""

    name = "stage_transfer"
    description = (
        "Create/stage an unfunded transfer in Wise linked to a locked quote UUID and recipient account. "
        "The transfer is queued in 'incoming_payment_waiting' status so the user can review and fund "
        "it in the Wise app, or explicitly execute funding via fund_transfer."
    )
    input_schema = StageTransferInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        transfer = await client.stage_transfer(
            arguments["target_account_id"],
            arguments["quote_uuid"],
            arguments["reference"],
            customer_transaction_id=arguments.get("customer_transaction_id"),
            transfer_purpose=arguments.get("transfer_purpose"),
            source_of_funds=arguments.get("source_of_funds"),
        )
        return transfer.model_dump()


class CancelTransferInput(ToolSchema):
    """Input schema for cancel_transfer tool."""

    transfer_id: int = Field(description="Unique transfer ID to cancel")


class CancelTransferTool(BaseTool):
    """Cancel an existing pending/unfunded transfer in Wise."""

    name = "cancel_transfer"
    description = (
        "Cancel an existing pending or unfunded transfer in Wise (e.g. in 'incoming_payment_waiting' status) "
        "before it is funded or processed."
    )
    input_schema = CancelTransferInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        transfer = await client.cancel_transfer(arguments["transfer_id"])
        return transfer.model_dump()


class FundTransferInput(ToolSchema):
    """Input schema for fund_transfer tool."""

    transfer_id: int = Field(
        description="Transfer ID to fund from Wise balance"
    )
    balance_id: int | None = Field(
        default=None,
        description="Optional source balance ID matching the source currency",
    )
    profile_id: int | None = Field(
        default=None,
        description="Profile ID executing the payment (optional if configured in server environment)",
    )


class FundTransferTool(BaseTool):
    """Fund a staged transfer from a Wise multi-currency balance."""

    name = "fund_transfer"
    description = (
        "Fund and execute an existing pending transfer using money from a Wise multi-currency balance. "
        "HIGH-RISK FINANCIAL OPERATION: Irrevocably executes outbound bank payment."
    )
    input_schema = FundTransferInput

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

        result = await client.fund_transfer(
            profile_id,
            arguments["transfer_id"],
            balance_id=arguments.get("balance_id"),
        )
        return result.model_dump()
