from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from digitalcard.models.marketing import CampaignStatus, SubmissionStatus


class FormField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=80)
    type: Literal["text", "email", "phone", "textarea", "select"]
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=30)


class FormPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    fields: list[FormField] = Field(min_length=1, max_length=30)
    privacy_notice: str = Field(min_length=1, max_length=3000)
    success_message: str = Field(min_length=1, max_length=500)
    is_active: bool = True

    @model_validator(mode="after")
    def unique_fields(self):  # type: ignore[no-untyped-def]
        keys = [item.key for item in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Field keys must be unique")
        if not any(item.key == "contact" for item in self.fields):
            raise ValueError("A contact field is required")
        return self


class FormResponse(FormPayload):
    model_config = ConfigDict(from_attributes=True)
    id: str
    revision: int
    created_at: datetime
    updated_at: datetime


class CampaignPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form_id: str
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=3000)
    card_id: str | None = None
    product_id: str | None = None
    owner_employee_id: str | None = None
    channel: str = Field(default="direct", pattern=r"^[\w-]+$", max_length=64)
    starts_at: datetime
    ends_at: datetime
    capacity: int | None = Field(default=None, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def valid_period(self):  # type: ignore[no-untyped-def]
        if self.ends_at <= self.starts_at:
            raise ValueError("Campaign end must be after start")
        return self


class CampaignResponse(CampaignPayload):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: CampaignStatus
    submission_count: int
    created_at: datetime
    updated_at: datetime


class PublicCampaignResponse(BaseModel):
    id: str
    name: str
    description: str | None
    channel: str
    starts_at: datetime
    ends_at: datetime
    remaining: int | None
    state: Literal["open", "not_started", "ended", "full", "closed"]
    fields: list[FormField]
    privacy_notice: str
    success_message: str


class PublicSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, str]
    privacy_agreed: Literal[True]
    source: str | None = Field(default=None, max_length=64, pattern=r"^[\w-]+$")
    website: str = Field(default="", max_length=200)


class PublicSubmissionResponse(BaseModel):
    id: str
    duplicate: bool
    message: str


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    campaign_id: str
    lead_id: str | None
    form_revision: int
    form_snapshot: dict[str, object]
    values: dict[str, object]
    channel: str
    status: SubmissionStatus
    created_at: datetime


class SubmissionPage(BaseModel):
    items: list[SubmissionResponse]
    total: int


class CampaignStats(BaseModel):
    submissions: int
    converted: int
    invalid: int
    conversion_rate: float
    channels: dict[str, int]
