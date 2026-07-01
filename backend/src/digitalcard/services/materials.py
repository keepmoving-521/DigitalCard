from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from digitalcard.core.config import Settings
from digitalcard.core.errors import AppError
from digitalcard.models.product import Material, MaterialKind, Product

MIME_TYPES: dict[str, tuple[MaterialKind, str]] = {
    "image/jpeg": (MaterialKind.IMAGE, ".jpg"),
    "image/png": (MaterialKind.IMAGE, ".png"),
    "image/webp": (MaterialKind.IMAGE, ".webp"),
    "video/mp4": (MaterialKind.VIDEO, ".mp4"),
    "video/webm": (MaterialKind.VIDEO, ".webm"),
    "application/pdf": (MaterialKind.PDF, ".pdf"),
}


def material_type(mime_type: str) -> tuple[MaterialKind, str]:
    value = MIME_TYPES.get(mime_type.lower().split(";", maxsplit=1)[0].strip())
    if value is None:
        raise AppError(
            "material_type_not_allowed",
            "Only JPEG, PNG, WebP, MP4, WebM and PDF files are supported",
            415,
        )
    return value


def max_size_for(kind: MaterialKind, settings: Settings) -> int:
    return {
        MaterialKind.IMAGE: settings.image_max_bytes,
        MaterialKind.VIDEO: settings.video_max_bytes,
        MaterialKind.PDF: settings.pdf_max_bytes,
    }[kind]


def valid_signature(mime_type: str, header: bytes) -> bool:
    checks = {
        "image/jpeg": header.startswith(b"\xff\xd8\xff"),
        "image/png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        "video/mp4": len(header) >= 12 and header[4:8] == b"ftyp",
        "video/webm": header.startswith(b"\x1aE\xdf\xa3"),
        "application/pdf": header.startswith(b"%PDF-"),
    }
    return checks.get(mime_type, False)


def storage_path(settings: Settings, storage_key: str) -> Path:
    root = Path(settings.upload_dir).resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise AppError("invalid_storage_key", "Material storage key is invalid", 500)
    return path


def tenant_material(db: Session, company_id: str, material_id: str) -> Material:
    material = db.scalar(
        select(Material).where(Material.id == material_id, Material.company_id == company_id)
    )
    if material is None:
        raise AppError("material_not_found", "Material was not found", 404)
    return material


def material_references(db: Session, company_id: str, material_id: str) -> list[dict[str, str]]:
    products = list(
        db.scalars(
            select(Product).where(
                Product.company_id == company_id,
                or_(
                    Product.cover_material_id == material_id,
                    Product.video_material_id == material_id,
                ),
            )
        )
    )
    for product in db.scalars(select(Product).where(Product.company_id == company_id)):
        if (
            material_id in product.gallery_material_ids
            or material_id in product.attachment_material_ids
        ) and all(existing.id != product.id for existing in products):
            products.append(product)
    return [{"type": "product", "id": product.id, "name": product.name} for product in products]
