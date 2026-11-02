"""Pydantic models for Wise Transfer Payments (funding)."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class PaymentResponse(BaseModel):
    """Result of funding a Wise transfer."""

    model_config = ConfigDict(extra="ignore")

    type: str = Field(description="Funding payment method, typically 'BALANCE'")
    status: str = Field(
        description="Payment status (e.g. 'COMPLETED', 'WAITING_FOR_FUNDS', 'PROCESSING')"
    )
    balanceId: int | None = Field(
        default=None, description="Source balance ID debited for this payment"
    )
    details: dict[str, Any] | None = Field(
        default=None, description="Detailed payment processing metadata"
    )
