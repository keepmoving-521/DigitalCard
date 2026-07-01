from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from digitalcard.models.saas import SubscriptionStatus


class PlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    name: str = Field(min_length=1, max_length=120)
    employee_limit: int = Field(ge=1, le=1_000_000)
    card_limit: int = Field(ge=1, le=1_000_000)
    storage_limit_bytes: int = Field(ge=1, le=10_000_000_000_000)
    is_active: bool = True


class PlanResponse(PlanPayload):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    expires_at: datetime
    note: str | None = Field(default=None, max_length=500)


class SubscriptionResponse(BaseModel):
    company_id: str
    plan_id: str
    plan_name: str
    status: SubscriptionStatus
    starts_at: datetime
    expires_at: datetime
    cancel_requested_at: datetime | None
    cancel_effective_at: datetime | None
    data_cleanup_after: datetime | None
    usage: dict[str, int]
    limits: dict[str, int]
    warnings: list[str]


class CancelRequest(BaseModel):
    confirmation: str
    cooling_days: int = Field(default=7, ge=1, le=90)


class SupportGrantRequest(BaseModel):
    company_id: str
    granted_to_user_id: str
    reason: str = Field(min_length=5, max_length=500)
    expires_at: datetime

    @model_validator(mode="after")
    def future_expiry(self):  # type: ignore[no-untyped-def]
        if self.expires_at <= datetime.utcnow():
            raise ValueError("Grant expiry must be in the future")
        return self


class TenantOverview(BaseModel):
    company_id: str
    company_name: str
    company_status: str
    subscription: SubscriptionResponse
    alerts: list[str]
