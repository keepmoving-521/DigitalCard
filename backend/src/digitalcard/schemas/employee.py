import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from digitalcard.models.account import UserRole
from digitalcard.models.employee import EmployeeStatus
from digitalcard.schemas.account import normalize_email


def normalize_employee_no(value: str) -> str:
    employee_no = value.strip().upper()
    if not employee_no or len(employee_no) > 64:
        raise ValueError("Employee number must contain 1-64 characters")
    return employee_no


def normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    phone = re.sub(r"[\s()\-]", "", value)
    if not re.fullmatch(r"\+?\d{6,20}", phone):
        raise ValueError("Phone number must contain 6-20 digits with an optional leading +")
    return phone


def normalize_optional_email(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return normalize_email(value)


class EmployeeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_no: str
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None
    email: str | None = None
    avatar_url: str | None = Field(default=None, max_length=1024)
    bio: str | None = Field(default=None, max_length=5000)
    position: str | None = Field(default=None, max_length=100)
    department_id: str | None = None
    manager_id: str | None = None
    user_id: str | None = None

    _normalize_employee_no = field_validator("employee_no")(normalize_employee_no)
    _normalize_phone = field_validator("phone")(normalize_phone)
    _normalize_email = field_validator("email")(normalize_optional_email)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class EmployeeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_no: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = None
    email: str | None = None
    avatar_url: str | None = Field(default=None, max_length=1024)
    bio: str | None = Field(default=None, max_length=5000)
    position: str | None = Field(default=None, max_length=100)
    department_id: str | None = None
    manager_id: str | None = None
    user_id: str | None = None

    @field_validator("employee_no")
    @classmethod
    def normalize_optional_employee_no(cls, value: str | None) -> str | None:
        return normalize_employee_no(value) if value is not None else None

    _normalize_phone = field_validator("phone")(normalize_phone)
    _normalize_email = field_validator("email")(normalize_optional_email)


class EmployeeSelfUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str | None = None
    email: str | None = None
    avatar_url: str | None = Field(default=None, max_length=1024)
    bio: str | None = Field(default=None, max_length=5000)

    _normalize_phone = field_validator("phone")(normalize_phone)
    _normalize_email = field_validator("email")(normalize_optional_email)


class EmployeeStatusRequest(BaseModel):
    status: EmployeeStatus


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    employee_no: str
    name: str
    phone: str | None
    email: str | None
    avatar_url: str | None
    bio: str | None
    position: str | None
    department_id: str | None
    manager_id: str | None
    user_id: str | None
    status: EmployeeStatus
    created_at: datetime
    updated_at: datetime


class EmployeePageResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    offset: int
    limit: int


class EmployeeImportRowResult(BaseModel):
    row: int
    status: str
    employee_id: str | None = None
    code: str | None = None
    message: str | None = None


class EmployeeImportResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[EmployeeImportRowResult]


class EmployeeInviteRequest(BaseModel):
    role: UserRole = UserRole.EMPLOYEE


class EmployeeInviteResponse(BaseModel):
    invitation_id: str
    invite_url: str
    expires_at: datetime
    delivery_status: str = "link_generated"


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=12, max_length=256)


class PublicEmployeeResponse(BaseModel):
    id: str
    name: str
    avatar_url: str | None
    bio: str | None
    position: str | None
    employment_status: EmployeeStatus
