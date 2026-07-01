import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from digitalcard.models.product import MaterialAccess, MaterialKind, ProductStatus


class CategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=999999)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]+", code):
            raise ValueError("Category code may contain letters, numbers, underscores and hyphens")
        return code


class CategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0, le=999999)
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    code: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MaterialAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access: MaterialAccess


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    name: str
    kind: MaterialKind
    mime_type: str
    size_bytes: int
    access: MaterialAccess
    created_at: datetime
    updated_at: datetime


def unique_ids(value: list[str]) -> list[str]:
    if len(value) != len(set(value)):
        raise ValueError("Material IDs must not contain duplicates")
    return value


class ProductCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    category_id: str | None = None
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    specifications: dict[str, str] = Field(default_factory=dict)
    cover_material_id: str | None = None
    video_material_id: str | None = None
    gallery_material_ids: list[str] = Field(default_factory=list, max_length=20)
    attachment_material_ids: list[str] = Field(default_factory=list, max_length=20)
    video_url: str | None = Field(default=None, max_length=1024)
    sort_order: int = Field(default=0, ge=0, le=999999)

    _gallery_unique = field_validator("gallery_material_ids")(unique_ids)
    _attachment_unique = field_validator("attachment_material_ids")(unique_ids)

    @field_validator("specifications")
    @classmethod
    def validate_specifications(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 50 or any(
            not key.strip() or len(key) > 80 or len(item) > 500 for key, item in value.items()
        ):
            raise ValueError("Specifications contain too many or oversized values")
        return {key.strip(): item.strip() for key, item in value.items()}

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not re.fullmatch(r"https?://[^\s]+", value, re.IGNORECASE):
            raise ValueError("Video URL must start with http:// or https://")
        return value


class ProductUpdateRequest(ProductCreateRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category_id: str | None = None
    specifications: dict[str, str] | None = None
    gallery_material_ids: list[str] | None = Field(default=None, max_length=20)
    attachment_material_ids: list[str] | None = Field(default=None, max_length=20)
    sort_order: int | None = Field(default=None, ge=0, le=999999)


class ProductStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ProductStatus


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    category_id: str | None
    name: str
    summary: str | None
    description: str | None
    specifications: dict[str, str]
    cover_material_id: str | None
    video_material_id: str | None
    gallery_material_ids: list[str]
    attachment_material_ids: list[str]
    video_url: str | None
    status: ProductStatus
    sort_order: int
    published_at: datetime | None
    offline_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductPageResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    offset: int
    limit: int


class CardRecommendationsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_ids: list[str] = Field(max_length=20)

    _unique = field_validator("product_ids")(unique_ids)


class CardRecommendationsResponse(BaseModel):
    product_ids: list[str]
    has_unpublished_changes: bool


class PublicProductSummary(BaseModel):
    id: str
    name: str
    summary: str | None
    category_id: str | None
    cover_url: str | None
    sort_order: int


class PublicProductDetail(PublicProductSummary):
    description: str | None
    specifications: dict[str, str]
    gallery_urls: list[str]
    video_url: str | None
    attachment_urls: list[str]
