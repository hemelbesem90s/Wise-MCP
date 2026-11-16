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
    icon: Any = Field(
        default=None, description="Optional icon identifier or emoji object"
    )


class BalanceMovement(BaseModel):
    """Wise internal balance movement or jar transfer."""

    model_config = ConfigDict(extra="allow")

    id: int | str | None = Field(default=None, description="Unique movement identifier")
    state: str | None = Field(
        default=None, description="Lifecycle state of the movement"
    )
    status: str | None = Field(default=None, description="Status alias of the movement")
    sourceBalanceId: int | None = Field(
        default=None, description="Source balance or jar ID"
    )
    targetBalanceId: int | None = Field(
        default=None, description="Target balance or jar ID"
    )
    sourceAmount: BalanceAmount | dict[str, Any] | None = Field(
        default=None, description="Amount debited from source balance"
    )
    targetAmount: BalanceAmount | dict[str, Any] | None = Field(
        default=None, description="Amount credited to target balance"
    )
    quoteId: str | int | None = Field(
        default=None, description="FX quote ID if cross-currency conversion"
    )
    steps: list[Any] | None = Field(
        default=None, description="Execution steps of the movement"
    )
    createdOn: str | None = Field(default=None, description="Creation timestamp")
    updatedOn: str | None = Field(default=None, description="Update timestamp")
