"""Pydantic models for Wise Profiles."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

ProfileType = Literal["personal", "business"]


class Profile(BaseModel):
    """Wise Profile (personal or business)."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Unique profile ID")
    type: ProfileType = Field(description="Profile type ('personal' or 'business')")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Profile details (e.g. name, registration number, address)",
    )
    fullName: str | None = Field(default=None, description="Personal full name if personal profile")

    @property
    def display_name(self) -> str:
        """User-friendly display name for this profile."""
        if self.type == "business":
            name = self.details.get("name") or self.details.get("companyName")
            if name:
                return str(name)
        first = self.details.get("firstName") or ""
        last = self.details.get("lastName") or ""
        combined = f"{first} {last}".strip()
        if combined:
            return combined
        return self.fullName or f"Profile #{self.id}"
