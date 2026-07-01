from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.product import Material, MaterialAccess, Product, ProductStatus
from digitalcard.schemas.product import MaterialAccessRequest, MaterialResponse
from digitalcard.services.materials import (
    material_references,
    material_type,
    max_size_for,
    storage_path,
    tenant_material,
    valid_signature,
)
from digitalcard.services.permissions import Permission
from digitalcard.services.quotas import enforce_quota
from digitalcard.services.tenancy import record_tenant_audit

router = APIRouter(tags=["materials"])


@router.get("/tenant/materials", response_model=list[MaterialResponse], summary="List materials")
def list_materials(
    user: Annotated[User, Depends(require_permission(Permission.MATERIAL_READ))],
    db: Annotated[Session, Depends(get_db)],
    kind: str | None = None,
    access: MaterialAccess | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[Material]:
    query = select(Material).where(Material.company_id == user.company_id)
    if kind:
        query = query.where(Material.kind == kind)
    if access:
        query = query.where(Material.access == access.value)
    return list(db.scalars(query.order_by(Material.created_at.desc()).limit(limit)))


@router.post(
    "/tenant/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload material",
)
async def upload_material(
    request: Request,
    name: Annotated[str, Query(min_length=1, max_length=200)],
    access: MaterialAccess,
    user: Annotated[User, Depends(require_permission(Permission.MATERIAL_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Material:
    mime_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
    kind, extension = material_type(mime_type)
    maximum = max_size_for(kind, settings)
    material_id = str(uuid4())
    storage_key = f"{user.company_id}/{material_id}{extension}"
    final_path = storage_path(settings, storage_key)
    temporary_path = final_path.with_suffix(f"{final_path.suffix}.upload")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    committed = False
    try:
        with temporary_path.open("wb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > maximum:
                    raise AppError(
                        "material_too_large",
                        "File exceeds the configured size limit",
                        413,
                        {"maximum_bytes": maximum},
                    )
                output.write(chunk)
        if size == 0:
            raise AppError("material_empty", "Uploaded file is empty", 422)
        enforce_quota(db, user.company_id, "storage", size)
        with temporary_path.open("rb") as uploaded:
            if not valid_signature(mime_type, uploaded.read(16)):
                raise AppError(
                    "material_content_mismatch",
                    "File content does not match its declared type",
                    422,
                )
        temporary_path.replace(final_path)
        material = Material(
            id=material_id,
            company_id=user.company_id,
            name=name.strip(),
            kind=kind.value,
            mime_type=mime_type,
            size_bytes=size,
            storage_key=storage_key,
            access=access.value,
            created_by_user_id=user.id,
        )
        db.add(material)
        record_tenant_audit(
            db,
            user.company_id,
            user.id,
            "material.uploaded",
            "material",
            material.id,
            {"name": material.name, "kind": material.kind, "size_bytes": size},
        )
        db.commit()
        committed = True
        db.refresh(material)
        return material
    except Exception:
        temporary_path.unlink(missing_ok=True)
        if final_path.exists() and not committed:
            final_path.unlink(missing_ok=True)
        raise


@router.patch(
    "/tenant/materials/{material_id}/access",
    response_model=MaterialResponse,
    summary="Update material access",
)
def update_material_access(
    material_id: str,
    payload: MaterialAccessRequest,
    user: Annotated[User, Depends(require_permission(Permission.MATERIAL_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> Material:
    material = tenant_material(db, user.company_id, material_id)
    if payload.access == MaterialAccess.PRIVATE:
        published_references = [
            reference
            for reference in material_references(db, user.company_id, material.id)
            if db.get(Product, reference["id"]).status == ProductStatus.PUBLISHED.value
        ]
        if published_references:
            raise AppError(
                "material_in_published_product",
                "Published products still reference this material",
                409,
                {"references": published_references},
            )
    material.access = payload.access.value
    db.commit()
    db.refresh(material)
    return material


@router.delete(
    "/tenant/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete material",
)
def delete_material(
    material_id: str,
    user: Annotated[User, Depends(require_permission(Permission.MATERIAL_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    material = tenant_material(db, user.company_id, material_id)
    references = material_references(db, user.company_id, material.id)
    if references:
        raise AppError(
            "material_in_use",
            "Material is still referenced and cannot be deleted",
            409,
            {"references": references},
        )
    path = storage_path(settings, material.storage_key)
    db.delete(material)
    db.commit()
    path.unlink(missing_ok=True)


@router.get("/tenant/materials/{material_id}/content", summary="Read tenant material")
def read_tenant_material(
    material_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_permission(Permission.MATERIAL_READ))],
) -> FileResponse:
    material = tenant_material(db, user.company_id, material_id)
    path = storage_path(settings, material.storage_key)
    if not path.is_file():
        raise AppError("material_file_missing", "Material file is unavailable", 404)
    return FileResponse(path, media_type=material.mime_type, filename=material.name)


@router.get("/public/materials/{material_id}", summary="Read public material")
def read_public_material(
    material_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    material = db.get(Material, material_id)
    if material is None or material.access != MaterialAccess.PUBLIC.value:
        raise AppError("material_not_found", "Public material was not found", 404)
    path = storage_path(settings, material.storage_key)
    if not path.is_file():
        raise AppError("material_not_found", "Public material was not found", 404)
    return FileResponse(path, media_type=material.mime_type)
