from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.api.routes.public_cards import published_card
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.employee import Employee
from digitalcard.models.organization import Company, CompanyStatus
from digitalcard.models.product import (
    MaterialAccess,
    MaterialKind,
    Product,
    ProductCategory,
    ProductStatus,
)
from digitalcard.schemas.product import (
    CardRecommendationsRequest,
    CardRecommendationsResponse,
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    ProductCreateRequest,
    ProductPageResponse,
    ProductResponse,
    ProductStatusRequest,
    ProductUpdateRequest,
    PublicProductDetail,
    PublicProductSummary,
)
from digitalcard.services.cards import get_or_create_card
from digitalcard.services.employee_profiles import get_or_create_employee_for_user
from digitalcard.services.materials import tenant_material
from digitalcard.services.permissions import Permission
from digitalcard.services.tenancy import record_tenant_audit

router = APIRouter(tags=["products"])


def tenant_category(db: Session, company_id: str, category_id: str) -> ProductCategory:
    category = db.scalar(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.company_id == company_id,
        )
    )
    if category is None:
        raise AppError("product_category_not_found", "Product category was not found", 404)
    return category


def tenant_product(db: Session, company_id: str, product_id: str) -> Product:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.company_id == company_id)
    )
    if product is None:
        raise AppError("product_not_found", "Product was not found", 404)
    return product


def validate_product_relations(
    db: Session, company_id: str, values: dict[str, object], publishing: bool = False
) -> None:
    category_id = values.get("category_id")
    if category_id:
        category = tenant_category(db, company_id, str(category_id))
        if publishing and not category.is_active:
            raise AppError("product_category_inactive", "Product category is inactive", 409)
    definitions = (
        ("cover_material_id", MaterialKind.IMAGE),
        ("video_material_id", MaterialKind.VIDEO),
    )
    material_ids: list[tuple[str, MaterialKind]] = []
    for field, expected_kind in definitions:
        if values.get(field):
            material_ids.append((str(values[field]), expected_kind))
    material_ids.extend(
        (str(material_id), MaterialKind.IMAGE)
        for material_id in values.get("gallery_material_ids", []) or []
    )
    material_ids.extend(
        (str(material_id), MaterialKind.PDF)
        for material_id in values.get("attachment_material_ids", []) or []
    )
    for material_id, expected_kind in material_ids:
        material = tenant_material(db, company_id, material_id)
        if material.kind != expected_kind.value:
            raise AppError(
                "product_material_type_mismatch",
                "Product material has an incompatible file type",
                422,
                {"material_id": material.id, "expected_kind": expected_kind.value},
            )
        if publishing and material.access != MaterialAccess.PUBLIC.value:
            raise AppError(
                "product_material_not_public",
                "All materials must be public before publishing a product",
                409,
                {"material_id": material.id},
            )


def product_values(product: Product, changes: dict[str, object] | None = None) -> dict[str, object]:
    values = {
        "category_id": product.category_id,
        "cover_material_id": product.cover_material_id,
        "video_material_id": product.video_material_id,
        "gallery_material_ids": product.gallery_material_ids,
        "attachment_material_ids": product.attachment_material_ids,
    }
    if changes:
        values.update(changes)
    return values


def validate_publishable_product(db: Session, product: Product) -> None:
    missing: list[str] = []
    if not product.cover_material_id:
        missing.append("cover_material_id")
    if not (product.summary or product.description):
        missing.append("summary_or_description")
    if missing:
        raise AppError(
            "product_publish_validation_failed",
            "Product does not meet publishing requirements",
            422,
            {"missing": missing},
        )
    validate_product_relations(db, product.company_id, product_values(product), True)


@router.get(
    "/tenant/product-categories",
    response_model=list[CategoryResponse],
    summary="List product categories",
)
def list_categories(
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProductCategory]:
    return list(
        db.scalars(
            select(ProductCategory)
            .where(ProductCategory.company_id == user.company_id)
            .order_by(ProductCategory.sort_order, ProductCategory.created_at)
        )
    )


@router.post(
    "/tenant/product-categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product category",
)
def create_category(
    payload: CategoryCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> ProductCategory:
    if db.scalar(
        select(ProductCategory.id).where(
            ProductCategory.company_id == user.company_id,
            ProductCategory.code == payload.code,
        )
    ):
        raise AppError("product_category_code_exists", "Category code already exists", 409)
    category = ProductCategory(company_id=user.company_id, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch(
    "/tenant/product-categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update product category",
)
def update_category(
    category_id: str,
    payload: CategoryUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> ProductCategory:
    category = tenant_category(db, user.company_id, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.get("/tenant/products", response_model=ProductPageResponse, summary="List products")
def list_products(
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_READ))],
    db: Annotated[Session, Depends(get_db)],
    product_status: Annotated[ProductStatus | None, Query(alias="status")] = None,
    category_id: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductPageResponse:
    conditions = [Product.company_id == user.company_id]
    if product_status:
        conditions.append(Product.status == product_status.value)
    if category_id:
        conditions.append(Product.category_id == category_id)
    total = db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0
    items = list(
        db.scalars(
            select(Product)
            .where(*conditions)
            .order_by(Product.sort_order, Product.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return ProductPageResponse(items=items, total=total, offset=offset, limit=limit)


@router.post(
    "/tenant/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
)
def create_product(
    payload: ProductCreateRequest,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Product:
    values = payload.model_dump(mode="json")
    validate_product_relations(db, user.company_id, values)
    product = Product(company_id=user.company_id, **values)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/tenant/products/{product_id}", response_model=ProductResponse, summary="Get product")
def get_product(
    product_id: str,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> Product:
    return tenant_product(db, user.company_id, product_id)


@router.patch(
    "/tenant/products/{product_id}", response_model=ProductResponse, summary="Update product"
)
def update_product(
    product_id: str,
    payload: ProductUpdateRequest,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Product:
    product = tenant_product(db, user.company_id, product_id)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    publishing = product.status == ProductStatus.PUBLISHED.value
    merged = product_values(product, changes)
    validate_product_relations(db, user.company_id, merged, publishing)
    if publishing:
        missing: list[str] = []
        if not merged.get("cover_material_id"):
            missing.append("cover_material_id")
        summary = changes.get("summary", product.summary)
        description = changes.get("description", product.description)
        if not (summary or description):
            missing.append("summary_or_description")
        if missing:
            raise AppError(
                "product_publish_validation_failed",
                "Published product must continue to meet publishing requirements",
                422,
                {"missing": missing},
            )
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.post(
    "/tenant/products/{product_id}/status",
    response_model=ProductResponse,
    summary="Set product status",
)
def set_product_status(
    product_id: str,
    payload: ProductStatusRequest,
    user: Annotated[User, Depends(require_permission(Permission.PRODUCT_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Product:
    product = tenant_product(db, user.company_id, product_id)
    if payload.status == ProductStatus.PUBLISHED:
        validate_publishable_product(db, product)
        product.published_at = utc_now()
        product.offline_at = None
    elif payload.status == ProductStatus.OFFLINE:
        if product.published_at is None:
            raise AppError("product_not_published", "Product has not been published", 409)
        product.offline_at = utc_now()
    elif product.published_at is not None:
        raise AppError(
            "invalid_product_transition", "Published products cannot return to draft", 409
        )
    product.status = payload.status.value
    record_tenant_audit(
        db,
        user.company_id,
        user.id,
        "product.status_changed",
        "product",
        product.id,
        {"status": product.status},
    )
    db.commit()
    db.refresh(product)
    return product


def update_recommendations(
    db: Session, employee: Employee, payload: CardRecommendationsRequest, actor: User
) -> CardRecommendationsResponse:
    products = list(
        db.scalars(
            select(Product).where(
                Product.company_id == employee.company_id,
                Product.id.in_(payload.product_ids),
                Product.status == ProductStatus.PUBLISHED.value,
            )
        )
    )
    if len(products) != len(payload.product_ids):
        raise AppError(
            "recommended_product_unavailable",
            "All recommended products must be published in the current company",
            422,
        )
    card = get_or_create_card(db, employee)
    draft = dict(card.draft_data)
    draft["recommended_product_ids"] = list(payload.product_ids)
    card.draft_data = draft
    card.draft_revision += 1
    record_tenant_audit(
        db,
        employee.company_id,
        actor.id,
        "card.product_recommendations_updated",
        "digital_card",
        card.id,
        {"product_ids": payload.product_ids},
    )
    db.commit()
    return CardRecommendationsResponse(
        product_ids=payload.product_ids, has_unpublished_changes=True
    )


@router.put(
    "/tenant/cards/me/recommendations",
    response_model=CardRecommendationsResponse,
    summary="Update my recommended products",
)
def update_my_recommendations(
    payload: CardRecommendationsRequest,
    user: Annotated[User, Depends(require_permission(Permission.CARD_EDIT_SELF))],
    db: Annotated[Session, Depends(get_db)],
) -> CardRecommendationsResponse:
    return update_recommendations(db, get_or_create_employee_for_user(db, user), payload, user)


@router.put(
    "/tenant/cards/{employee_id}/recommendations",
    response_model=CardRecommendationsResponse,
    summary="Update employee recommended products",
)
def update_employee_recommendations(
    employee_id: str,
    payload: CardRecommendationsRequest,
    user: Annotated[User, Depends(require_permission(Permission.CARD_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> CardRecommendationsResponse:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.company_id == user.company_id)
    )
    if employee is None:
        raise AppError("employee_not_found", "Employee was not found", 404)
    return update_recommendations(db, employee, payload, user)


def public_material_url(material_id: str | None) -> str | None:
    return f"/api/v1/public/materials/{material_id}" if material_id else None


def public_product_summary(product: Product) -> PublicProductSummary:
    return PublicProductSummary(
        id=product.id,
        name=product.name,
        summary=product.summary,
        category_id=product.category_id,
        cover_url=public_material_url(product.cover_material_id),
        sort_order=product.sort_order,
    )


@router.get(
    "/public/cards/{card_id}/products",
    response_model=list[PublicProductSummary],
    summary="List card recommended products",
)
def list_public_card_products(
    card_id: str, db: Annotated[Session, Depends(get_db)]
) -> list[PublicProductSummary]:
    card = published_card(db, card_id)
    product_ids = list(card.published_data.get("recommended_product_ids", []))
    if not product_ids:
        return []
    products = {
        product.id: product
        for product in db.scalars(
            select(Product).where(
                Product.company_id == card.company_id,
                Product.id.in_(product_ids),
                Product.status == ProductStatus.PUBLISHED.value,
            )
        )
    }
    return [public_product_summary(products[item]) for item in product_ids if item in products]


@router.get(
    "/public/products/{product_id}",
    response_model=PublicProductDetail,
    summary="Get public product",
)
def get_public_product(
    product_id: str, db: Annotated[Session, Depends(get_db)]
) -> PublicProductDetail:
    product = db.get(Product, product_id)
    if product is None or product.status != ProductStatus.PUBLISHED.value:
        raise AppError("product_not_found", "Published product was not found", 404)
    company = db.get(Company, product.company_id)
    if company is None or company.status != CompanyStatus.ACTIVE.value:
        raise AppError("product_not_found", "Published product was not found", 404)
    summary = public_product_summary(product)
    return PublicProductDetail(
        **summary.model_dump(),
        description=product.description,
        specifications=product.specifications,
        gallery_urls=[public_material_url(item) for item in product.gallery_material_ids],
        video_url=public_material_url(product.video_material_id) or product.video_url,
        attachment_urls=[public_material_url(item) for item in product.attachment_material_ids],
    )
