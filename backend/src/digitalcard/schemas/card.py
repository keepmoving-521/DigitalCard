import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from digitalcard.models.card import CardStatus

MODULES = {"profile", "contact", "social", "bio"}
PERSONALIZATION_FIELDS = {"theme_color", "logo_url", "module_order"}
CONTENT_FIELDS = {
    "display_name",
    "headline",
    "avatar_url",
    "bio",
    "phone",
    "email",
    "wechat",
    "website",
    "socials",
    *PERSONALIZATION_FIELDS,
}


def validate_http_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if not re.fullmatch(r"https?://[^\s]+", value, re.IGNORECASE):
        raise ValueError("URL must start with http:// or https://")
    return value


def validate_theme(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"#[0-9a-f]{6}", value):
        raise ValueError("Theme color must be a six-digit hex color")
    return value


def validate_modules(value: list[str]) -> list[str]:
    if not value or len(value) != len(set(value)) or set(value) != MODULES:
        raise ValueError("Module order must contain profile, contact, social and bio once")
    return value


class SocialLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: str = Field(min_length=1, max_length=40)
    url: str

    _url = field_validator("url")(validate_http_url)


class CardTemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    theme_color: str
    logo_url: str | None = Field(default=None, max_length=1024)
    module_order: list[str]
    locked_fields: list[str]
    employee_editable_fields: list[str]

    _theme = field_validator("theme_color")(validate_theme)
    _logo = field_validator("logo_url")(validate_http_url)
    _modules = field_validator("module_order")(validate_modules)

    @field_validator("locked_fields")
    @classmethod
    def validate_locked_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or not set(value) <= PERSONALIZATION_FIELDS:
            raise ValueError("Locked fields contain unsupported values")
        return value

    @field_validator("employee_editable_fields")
    @classmethod
    def validate_editable_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or not set(value) <= CONTENT_FIELDS:
            raise ValueError("Editable fields contain unsupported values")
        return value


class CardTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    name: str
    theme_color: str
    logo_url: str | None
    module_order: list[str]
    locked_fields: list[str]
    employee_editable_fields: list[str]
    revision: int
    created_at: datetime
    updated_at: datetime


class CardDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    headline: str | None = Field(default=None, max_length=160)
    avatar_url: str | None = Field(default=None, max_length=1024)
    bio: str | None = Field(default=None, max_length=5000)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=320)
    wechat: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=1024)
    socials: list[SocialLink] | None = Field(default=None, max_length=20)
    theme_color: str | None = None
    logo_url: str | None = Field(default=None, max_length=1024)
    module_order: list[str] | None = None

    _avatar = field_validator("avatar_url")(validate_http_url)
    _website = field_validator("website")(validate_http_url)
    _logo = field_validator("logo_url")(validate_http_url)

    @field_validator("theme_color")
    @classmethod
    def validate_optional_theme(cls, value: str | None) -> str | None:
        return validate_theme(value) if value is not None else None

    @field_validator("module_order")
    @classmethod
    def validate_optional_modules(cls, value: list[str] | None) -> list[str] | None:
        return validate_modules(value) if value is not None else None


class DigitalCardResponse(BaseModel):
    id: str
    company_id: str
    employee_id: str
    status: CardStatus
    draft_data: dict[str, object]
    published_data: dict[str, object] | None
    draft_revision: int
    published_revision: int | None
    has_unpublished_changes: bool
    published_at: datetime | None
    offline_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CardPreviewResponse(BaseModel):
    card_id: str
    status: CardStatus
    data: dict[str, object]
    has_unpublished_changes: bool


class PublicCardResponse(BaseModel):
    card_id: str
    employee_id: str
    data: dict[str, object]
    published_at: datetime
