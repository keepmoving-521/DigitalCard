import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from digitalcard.models.lead import LeadStatus


class PublicLeadCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    contact: str = Field(min_length=5, max_length=320)
    demand: str | None = Field(default=None, max_length=3000)
    privacy_agreed: Literal[True]
    source: str = Field(default="direct", min_length=1, max_length=64, pattern=r"^[\w-]+$")
    product_id: str | None = Field(default=None, max_length=36)

    @field_validator("name", "contact", "demand")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, value: str) -> str:
        if "@" in value:
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                raise ValueError("Contact email is invalid")
        elif len(re.sub(r"\D", "", value)) < 6:
            raise ValueError("Contact phone is invalid")
        return value


class PublicLeadCreateResponse(BaseModel):
    id: str
    duplicate: bool
    message: str


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    card_id: str
    product_id: str | None
    owner_employee_id: str
    assigned_employee_id: str | None
    name: str
    contact: str
    demand: str | None
    source: str
    status: LeadStatus
    duplicate_count: int
    last_submitted_at: datetime
    claimed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LeadPageResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    offset: int
    limit: int


class LeadAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str = Field(min_length=1, max_length=36)


class LeadStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal[LeadStatus.CONTACTED, LeadStatus.INVALID]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    title: str
    content: str
    related_type: str | None
    related_id: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPageResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int
