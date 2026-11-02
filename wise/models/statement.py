"""Pydantic models for Wise Balance Statements."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class StatementAmount(BaseModel):
    """Monetary amount within a statement line."""

    model_config = ConfigDict(extra="ignore")

    value: float = Field(description="Numerical amount")
    currency: str = Field(description="Currency code")


class StatementLine(BaseModel):
    """Individual transaction line in a balance statement."""

    model_config = ConfigDict(extra="ignore")

    type: str = Field(description="Transaction type (DEBIT, CREDIT, FEE, etc.)")
    date: str = Field(description="Transaction date-time (ISO 8601)")
    amount: StatementAmount = Field(description="Transaction amount")
    totalFees: StatementAmount | None = Field(default=None, description="Fees charged")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed transaction context (description, counterparty, reference)",
    )
    runningBalance: StatementAmount | None = Field(
        default=None, description="Balance after this transaction"
    )


class BalanceStatement(BaseModel):
    """Parsed Wise balance statement."""

    model_config = ConfigDict(extra="ignore")

    accountHolder: dict[str, Any] | None = Field(
        default=None, description="Account holder profile metadata"
    )
    balance: dict[str, Any] | None = Field(
        default=None, description="Balance metadata"
    )
    query: dict[str, Any] | None = Field(
        default=None, description="Statement query parameters"
    )
    transactions: list[StatementLine] = Field(
        default_factory=list, description="Statement transaction lines"
    )
