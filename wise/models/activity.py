"""Pydantic models for Wise profile activities feed."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def strip_html_tags(text: str | None) -> str:
    """Strip HTML markup tags (e.g. <strong>, <positive>) and normalize whitespace.

    Args:
        text: Raw string potentially containing inline HTML tags.

    Returns:
        Clean plain text string.
    """
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return " ".join(clean.split()).strip()


class ActivityResource(BaseModel):
    """Resource reference for an activity item."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    id: str | int | None = None


class Activity(BaseModel):
    """Individual Wise profile activity entry."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Unique activity ID")
    type: str = Field(
        description="Activity type (e.g. TRANSFER, CARD_PAYMENT, INTERBALANCE, BALANCE_CASHBACK)"
    )
    resource: ActivityResource | dict[str, Any] | None = Field(
        default=None, description="Linked underlying resource"
    )
    title: str = Field(default="", description="Original title with inline HTML tags")
    title_text: str = Field(
        default="", description="Clean human-readable title without HTML formatting"
    )
    description: str = Field(
        default="", description="Original description with inline HTML tags"
    )
    description_text: str = Field(
        default="",
        description="Clean human-readable description without HTML formatting",
    )
    primaryAmount: str = Field(
        default="", description="Primary monetary amount and currency"
    )
    secondaryAmount: str = Field(
        default="", description="Secondary/converted monetary amount"
    )
    status: str = Field(
        default="", description="Activity status (e.g. COMPLETED, CANCELLED)"
    )
    createdOn: str = Field(default="", description="Creation timestamp")
    updatedOn: str = Field(default="", description="Update timestamp")

    @model_validator(mode="before")
    @classmethod
    def populate_stripped_text(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("title_text") and data.get("title"):
                data["title_text"] = strip_html_tags(data.get("title"))
            if not data.get("description_text") and data.get("description"):
                data["description_text"] = strip_html_tags(data.get("description"))
        return data


class ActivityResponse(BaseModel):
    """Activity feed response containing paginated activities and cursor."""

    model_config = ConfigDict(extra="allow")

    cursor: str | None = Field(
        default=None, description="Cursor for the next page of activities"
    )
    activities: list[Activity] = Field(
        default_factory=list, description="List of activity items"
    )
