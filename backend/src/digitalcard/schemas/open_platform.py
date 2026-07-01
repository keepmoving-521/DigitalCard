from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

OPEN_SCOPES = {"leads.write", "customers.read", "customers.write"}
WEBHOOK_EVENTS = {"lead.created", "customer.updated"}


class MessagePreferencePayload(BaseModel):
    new_lead: bool = True
    follow_up_due: bool = True
    quota_warning: bool = True


class MessagePreferenceResponse(MessagePreferencePayload):
    model_config = ConfigDict(from_attributes=True)
    user_id: str
    updated_at: datetime


class ApplicationPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=1, max_length=10)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    app_key: str
    scopes: list[str]
    rate_limit_per_minute: int
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class ApplicationCredentialResponse(ApplicationResponse):
    app_secret: str
    warning: str = "凭据仅完整展示一次，请立即安全保存。"


class ApplicationStatusPayload(BaseModel):
    is_active: bool


class WebhookPayload(BaseModel):
    target_url: HttpUrl
    events: list[str] = Field(min_length=1, max_length=10)


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    application_id: str
    target_url: str
    events: list[str]
    is_active: bool
    created_at: datetime


class WebhookCredentialResponse(WebhookResponse):
    signing_secret: str
    warning: str = "签名密钥仅展示一次。"


class OpenLeadRequest(BaseModel):
    card_id: str
    product_id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    contact: str = Field(min_length=5, max_length=320)
    demand: str | None = Field(default=None, max_length=3000)
    source: str = Field(default="open_api", max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=100)


class OpenCustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    tags: list[str] | None = None
