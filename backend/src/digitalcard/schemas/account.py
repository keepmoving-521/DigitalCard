import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from digitalcard.models.account import UserRole

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("A valid email address is required")
    return email


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=256)

    _normalize_email = field_validator("email")(normalize_email)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    role: UserRole
    company_id: str | None
    department_id: str | None
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CurrentUserResponse(UserResponse):
    permissions: list[str]


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUserResponse


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class UserCreateRequest(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=256)
    role: UserRole = UserRole.EMPLOYEE
    company_id: str | None = None
    department_id: str | None = None
    must_change_password: bool = True

    _normalize_email = field_validator("email")(normalize_email)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        return value.strip()


class UserStatusRequest(BaseModel):
    is_active: bool


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=256)
    must_change_password: bool = True


class LoginAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None
    email: str
    success: bool
    reason: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
