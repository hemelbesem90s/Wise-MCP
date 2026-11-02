"""Recipient tools for Wise MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from wise_mcp.tools.base import BaseTool, ToolSchema

if TYPE_CHECKING:
    from wise.client import WiseClient


class ListRecipientsInput(ToolSchema):
    """Input schema for list_recipients tool."""

    currency: str | None = Field(
        default=None,
        description="Filter recipients by 3-letter currency code (e.g. EUR, ZAR, USD)",
    )
    search: str | None = Field(
        default=None,
        description="Search substring to match in recipient name, IBAN, or account details",
    )
    profile_id: int | None = Field(
        default=None,
        description="Profile ID owning the recipients (optional if configured in server environment)",
    )


class ListRecipientsTool(BaseTool):
    """List and search beneficiary recipient bank accounts."""

    name = "list_recipients"
    description = (
        "List and search registered beneficiary recipient bank accounts by currency, legal name, "
        "or account details (IBAN, account number)."
    )
    input_schema = ListRecipientsInput

    async def execute(
        self, client: "WiseClient", arguments: dict[str, Any]
    ) -> dict[str, Any]:
        profile_id = arguments.get("profile_id") or client.config.profile_id
        recipients = await client.list_recipients(
            profile_id=profile_id,
            currency=arguments.get("currency"),
            search=arguments.get("search"),
        )
        return {
            "count": len(recipients),
            "recipients": [r.model_dump() for r in recipients],
        }


class CreateRecipientInput(ToolSchema):
    """Input schema for create_recipient tool."""

    account_holder_name: str = Field(
        description="Full legal name of beneficiary person or company"
    )
    currency: str = Field(description="3-letter target currency (e.g. EUR, ZAR, GBP, USD)")
    type: str = Field(
        description="Recipient account routing type (e.g. 'iban' for SEPA EUR/GBP, 'sort_code' for UK, 'south_africa', 'aba')"
    )
    details: dict[str, Any] = Field(
        description="Dictionary of bank identifiers (e.g. {'iban': 'DE89...'} or {'accountNumber': '...', 'branchCode': '...'})"
    )
    owned_by_customer: bool = Field(
        default=False,
        description="Set to true if destination account belongs to the profile owner themselves",
    )
    profile_id: int | None = Field(
        default=None,
        description="Profile ID registering the recipient (optional if configured in server environment)",
    )


class CreateRecipientTool(BaseTool):
    """Register a new beneficiary recipient bank account."""

    name = "create_recipient"
    description = (
        "Register a new beneficiary recipient bank account for outbound payouts. "
        "Supports SEPA IBAN (EUR), UK Sort Code & Account Number (GBP), South African local banks (ZAR), and US ACH (USD)."
    )
    input_schema = CreateRecipientInput

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

        recipient = await client.create_recipient(
            profile_id,
            arguments["account_holder_name"],
            arguments["currency"],
            arguments["type"],
            arguments["details"],
            owned_by_customer=arguments.get("owned_by_customer", False),
        )
        return recipient.model_dump()
