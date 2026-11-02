"""Pydantic models for Wise Recipients."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Recipient(BaseModel):
    """Wise recipient beneficiary bank account."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Unique recipient account ID")
    profile: int | None = Field(default=None, description="Profile ID owning this recipient")
    accountHolderName: str = Field(description="Full legal name of beneficiary or company")
    currency: str = Field(description="3-letter target currency code")
    country: str | None = Field(default=None, description="2-letter country code (ISO 3166-1)")
    type: str = Field(description="Account routing type (e.g. 'iban', 'sort_code', 'aba')")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed bank attributes (e.g. iban, bic, accountNumber, routingNumber)",
    )
    ownedByCustomer: bool | None = Field(
        default=None,
        description="Whether this account is owned by the profile owner themselves",
    )
    active: bool | None = Field(default=True, description="Whether recipient is active")
