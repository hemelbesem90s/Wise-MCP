"""Pydantic models for Wise Quotes."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Quote(BaseModel):
    """Wise Quote locking in exchange rate and fee structure."""

    model_config = ConfigDict(extra="ignore")

    id: Any = Field(description="Unique quote ID or UUID")
    sourceCurrency: str = Field(description="Currency to send")
    targetCurrency: str = Field(description="Currency to receive")
    sourceAmount: float | None = Field(default=None, description="Amount sent in source currency")
    targetAmount: float | None = Field(default=None, description="Amount received in target currency")
    rate: float = Field(description="Locked exchange rate")
    createdTime: str | None = Field(default=None, description="Creation timestamp (ISO 8601)")
    rateExpirationTime: str | None = Field(
        default=None, description="Expiration timestamp for guaranteed rate (ISO 8601)"
    )
    fee: float | None = Field(default=None, description="Total Wise fee")
    feeBreakdown: dict[str, Any] | None = Field(
        default=None, description="Itemized fee breakdown"
    )
    deliveryEstimate: str | None = Field(
        default=None, description="Estimated arrival time of funds"
    )
    paymentOptions: list[dict[str, Any]] | None = Field(
        default=None, description="Available pay-in options"
    )
