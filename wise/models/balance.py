"""Pydantic models for Wise multi-currency balances."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

BalanceType = Literal["STANDARD", "SAVINGS"]


class BalanceAmount(BaseModel):
    """Monetary amount representation."""

    model_config = ConfigDict(extra="ignore")

    value: float = Field(description="Numerical amount")
    currency: str = Field(description="3-letter currency code (e.g. EUR, USD, ZAR)")


class Balance(BaseModel):
    """Wise currency balance (standard balance or jar/savings)."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Unique balance ID")
    currency: str = Field(description="3-letter currency code")
    amount: BalanceAmount = Field(description="Total balance amount")
    reservedAmount: BalanceAmount | None = Field(
        default=None, description="Reserved amount pending completion"
    )
    cashAmount: BalanceAmount | None = Field(
        default=None, description="Liquid cash amount available"
    )
    totalWorth: BalanceAmount | None = Field(
        default=None, description="Total net worth of balance"
    )
    type: str = Field(
        default="STANDARD",
        description="Balance type: 'STANDARD' or 'SAVINGS' (jars)",
    )
    name: str | None = Field(
        default=None, description="Custom jar name (if type is SAVINGS)"
    )
    icon: Any = Field(default=None, description="Optional icon identifier or emoji object")
