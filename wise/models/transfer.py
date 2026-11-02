"""Pydantic models for Wise Transfers."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Transfer(BaseModel):
    """Wise payment transfer order."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Unique transfer ID")
    profile: int | None = Field(default=None, description="Profile ID executing transfer")
    targetAccount: int = Field(description="Recipient account ID")
    quoteUuid: str | None = Field(default=None, description="Locked quote UUID")
    status: str = Field(
        description=(
            "Transfer lifecycle status (e.g. 'incoming_payment_waiting', 'processing', "
            "'funds_converted', 'outgoing_payment_sent', 'cancelled')"
        )
    )
    reference: str | None = Field(
        default=None, description="Payment reference string shown on recipient statement"
    )
    rate: float | None = Field(default=None, description="Applied FX rate")
    created: str | None = Field(default=None, description="Creation timestamp (ISO 8601)")
    sourceValue: float | None = Field(
        default=None, description="Total amount sent in source currency"
    )
    targetValue: float | None = Field(
        default=None, description="Total amount received in target currency"
    )
    customerTransactionId: str | None = Field(
        default=None, description="Client idempotency tracking UUID"
    )
    details: dict[str, Any] | None = Field(
        default=None, description="Additional transfer details"
    )
