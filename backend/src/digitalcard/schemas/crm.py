from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from digitalcard.models.crm import CustomerStatus


class LeadConvertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    owner_employee_id: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))


class CustomerUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    tags: list[str] | None = Field(default=None, max_length=30)


class CustomerTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str


class ContactCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    contact_type: Literal["phone", "email", "wechat", "other"]
    contact_value: str = Field(min_length=1, max_length=320)
    position: str | None = Field(default=None, max_length=100)
    is_primary: bool = False
    sort_order: int = Field(default=0, ge=0, le=999999)


class ContactUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    contact_type: Literal["phone", "email", "wechat", "other"] | None = None
    contact_value: str | None = Field(default=None, min_length=1, max_length=320)
    position: str | None = Field(default=None, max_length=100)
    is_primary: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=999999)


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    contact_type: str
    contact_value: str
    position: str | None
    is_primary: bool
    sort_order: int
    created_at: datetime


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    owner_employee_id: str
    name: str
    primary_contact: str
    tags: list[str]
    status: CustomerStatus
    merged_into_id: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CustomerDetailResponse(CustomerResponse):
    contacts: list[ContactResponse]


class CustomerPageResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    offset: int
    limit: int


class FollowUpCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["phone", "wechat", "email", "meeting", "other"]
    content: str = Field(min_length=1, max_length=5000)
    occurred_at: datetime | None = None
    next_follow_up_at: datetime | None = None


class FollowUpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    customer_id: str
    created_by_user_id: str
    method: str
    content: str
    occurred_at: datetime
    next_follow_up_at: datetime | None
    created_at: datetime


class TimelineEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_type: str
    title: str
    details: dict[str, object]
    actor_user_id: str | None
    occurred_at: datetime


class StageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=999999)
    probability: int = Field(default=0, ge=0, le=100)
    is_won: bool = False
    is_lost: bool = False


class StageUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0, le=999999)
    probability: int | None = Field(default=None, ge=0, le=100)
    is_won: bool | None = None
    is_lost: bool | None = None
    is_active: bool | None = None


class StageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    sort_order: int
    probability: int
    is_won: bool
    is_lost: bool
    is_active: bool


class OpportunityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    stage_id: str
    expected_amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    expected_close_date: date | None = None


class OpportunityUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    stage_id: str | None = None
    expected_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    expected_close_date: date | None = None


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    customer_id: str
    owner_employee_id: str
    stage_id: str
    title: str
    expected_amount: Decimal
    expected_close_date: date | None
    created_at: datetime
    updated_at: datetime


class StageHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    from_stage_id: str | None
    to_stage_id: str
    actor_user_id: str | None
    changed_at: datetime


class MergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_customer_id: str


class MergePreviewResponse(BaseModel):
    target_customer_id: str
    source_customer_id: str
    conflicts: dict[str, list[str]]
    moved_counts: dict[str, int]


class FunnelItem(BaseModel):
    stage_id: str
    stage_name: str
    count: int
    expected_amount: Decimal


class FunnelResponse(BaseModel):
    items: list[FunnelItem]
