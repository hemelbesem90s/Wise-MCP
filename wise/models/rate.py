"""Pydantic models for Wise exchange rates."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExchangeRate(BaseModel):
    """Wise mid-market foreign exchange rate."""

    model_config = ConfigDict(extra="ignore")

    rate: float = Field(description="Mid-market FX exchange rate")
    source: str = Field(description="Source currency code (e.g. EUR)")
    target: str = Field(description="Target currency code (e.g. ZAR)")
    time: str = Field(description="Timestamp of rate quote (ISO 8601)")
