import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from digitalcard.models.account import UserRole
from digitalcard.models.organization import CompanyStatus

CODE_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")


def validate_code(value: str) -> str:
    code = value.strip().lower()
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("Code must contain 2-64 letters, numbers, underscores or hyphens")
    return code


class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    logo_url: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=5000)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class CompanyCreateRequest(CompanyBase):
    code: str

    _validate_code = field_validator("code")(validate_code)


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    logo_url: str | None = Field(default=None, max_length=1024)
    description: str | None = Field(default=None, max_length=5000)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)


class CompanyStatusRequest(BaseModel):
    status: CompanyStatus


class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    status: CompanyStatus
    created_at: datetime
    updated_at: datetime


class DepartmentCreateRequest(BaseModel):
    code: str
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    sort_order: int = Field(default=0, ge=0, le=1_000_000)

    _validate_code = field_validator("code")(validate_code)


class DepartmentUpdateRequest(BaseModel):
    code: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("code")
    @classmethod
    def validate_optional_code(cls, value: str | None) -> str | None:
        return validate_code(value) if value is not None else None


class DepartmentMoveRequest(BaseModel):
    parent_id: str | None = None
    sort_order: int = Field(default=0, ge=0, le=1_000_000)


class DepartmentStatusRequest(BaseModel):
    is_active: bool


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    code: str
    name: str
    parent_id: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentTreeNode(DepartmentResponse):
    children: list["DepartmentTreeNode"] = Field(default_factory=list)


class PermissionDefinitionResponse(BaseModel):
    code: str
    name: str
    category: str


class TenantRoleResponse(BaseModel):
    id: str
    code: UserRole
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]


class RolePermissionsUpdateRequest(BaseModel):
    permissions: list[str]


class TenantAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    actor_user_id: str | None
    action: str
    target_type: str
    target_id: str
    changes: dict[str, object] | None
    created_at: datetime
