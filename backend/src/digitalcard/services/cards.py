from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.core.errors import AppError
from digitalcard.models.card import CardTemplate, DigitalCard
from digitalcard.models.employee import Employee
from digitalcard.models.organization import Company
from digitalcard.services.quotas import enforce_quota


def get_or_create_template(db: Session, company: Company) -> CardTemplate:
    template = db.scalar(select(CardTemplate).where(CardTemplate.company_id == company.id))
    if template is None:
        template = CardTemplate(company_id=company.id, logo_url=company.logo_url)
        db.add(template)
        db.flush()
    return template


def initial_draft(employee: Employee) -> dict[str, object]:
    return {
        "display_name": employee.name,
        "headline": employee.position,
        "avatar_url": employee.avatar_url,
        "bio": employee.bio,
        "phone": employee.phone,
        "email": employee.email,
        "wechat": None,
        "website": None,
        "socials": [],
        "visible_fields": [
            "headline",
            "avatar_url",
            "bio",
            "phone",
            "email",
            "wechat",
            "website",
            "socials",
        ],
    }


def get_or_create_card(db: Session, employee: Employee) -> DigitalCard:
    card = db.scalar(select(DigitalCard).where(DigitalCard.employee_id == employee.id))
    if card is None:
        enforce_quota(db, employee.company_id, "cards")
        card = DigitalCard(
            company_id=employee.company_id,
            employee_id=employee.id,
            draft_data=initial_draft(employee),
        )
        db.add(card)
        db.flush()
    return card


def card_response(card: DigitalCard) -> dict[str, object]:
    return {
        "id": card.id,
        "company_id": card.company_id,
        "employee_id": card.employee_id,
        "status": card.status,
        "draft_data": card.draft_data,
        "published_data": card.published_data,
        "draft_revision": card.draft_revision,
        "published_revision": card.published_revision,
        "has_unpublished_changes": card.published_revision != card.draft_revision,
        "published_at": card.published_at,
        "offline_at": card.offline_at,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


def resolve_card_data(
    company: Company, template: CardTemplate, draft: dict[str, object]
) -> dict[str, object]:
    data: dict[str, object] = {
        "company_name": company.name,
        "theme_color": template.theme_color,
        "logo_url": template.logo_url,
        "module_order": list(template.module_order),
        "template_revision": template.revision,
    }
    data.update(
        {
            key: value
            for key, value in draft.items()
            if value is not None and key not in set(template.locked_fields)
        }
    )
    return data


def validate_publishable(data: dict[str, object]) -> None:
    missing: list[str] = []
    if not str(data.get("display_name") or "").strip():
        missing.append("display_name")
    if not (data.get("phone") or data.get("email")):
        missing.append("phone_or_email")
    module_order = data.get("module_order")
    if not isinstance(module_order, list) or not {"profile", "contact"} <= set(module_order):
        missing.append("module_order")
    invalid_images = [
        field
        for field in ("avatar_url", "logo_url")
        if data.get(field) and not str(data[field]).lower().startswith(("http://", "https://"))
    ]
    if missing or invalid_images:
        raise AppError(
            "card_publish_validation_failed",
            "Card does not meet publishing requirements",
            422,
            {"missing": missing, "invalid_images": invalid_images},
        )


def public_snapshot(data: dict[str, object]) -> dict[str, object]:
    always_public = {
        "company_name",
        "display_name",
        "theme_color",
        "logo_url",
        "module_order",
        "template_revision",
        "recommended_product_ids",
    }
    selectable = set(data.get("visible_fields") or [])
    return {
        key: value
        for key, value in data.items()
        if key in always_public or (key in selectable and value is not None)
    }
