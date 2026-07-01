import csv
import hashlib
import io
import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.card import DigitalCard
from digitalcard.models.employee import Employee
from digitalcard.models.lead import Lead, LeadStatus
from digitalcard.models.marketing import (
    Campaign,
    CampaignStatus,
    CampaignSubmission,
    MarketingForm,
    SubmissionStatus,
)
from digitalcard.models.product import Product
from digitalcard.schemas.marketing import (
    CampaignPayload,
    CampaignResponse,
    CampaignStats,
    FormPayload,
    FormResponse,
    PublicCampaignResponse,
    PublicSubmissionRequest,
    PublicSubmissionResponse,
    SubmissionPage,
)
from digitalcard.services.analytics import add_business_event, is_bot_user_agent
from digitalcard.services.permissions import Permission

router = APIRouter(tags=["marketing"])


def owned(db: Session, model, object_id: str, company_id: str):  # type: ignore[no-untyped-def]
    item = db.scalar(select(model).where(model.id == object_id, model.company_id == company_id))
    if item is None:
        raise AppError("marketing_not_found", "Marketing resource was not found", 404)
    return item


def campaign_state(item: Campaign) -> str:
    now = utc_now()
    if item.status != CampaignStatus.PUBLISHED.value:
        return "closed"
    if now < item.starts_at:
        return "not_started"
    if now >= item.ends_at:
        return "ended"
    if item.capacity is not None and item.submission_count >= item.capacity:
        return "full"
    return "open"


def public_campaign(db: Session, slug: str) -> tuple[Campaign, MarketingForm]:
    campaign = db.scalar(select(Campaign).where(Campaign.slug == slug))
    if campaign is None:
        raise AppError("campaign_not_found", "Campaign was not found", 404)
    form = db.get(MarketingForm, campaign.form_id)
    if form is None or not form.is_active:
        raise AppError("campaign_closed", "Campaign is unavailable", 410)
    return campaign, form


@router.get("/tenant/marketing/forms", response_model=list[FormResponse])
def list_forms(
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(
        db.scalars(
            select(MarketingForm)
            .where(MarketingForm.company_id == user.company_id)
            .order_by(MarketingForm.updated_at.desc())
        )
    )


@router.post("/tenant/marketing/forms", response_model=FormResponse, status_code=201)
def create_form(
    payload: FormPayload,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    item = MarketingForm(company_id=user.company_id, **payload.model_dump(mode="json"))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/tenant/marketing/forms/{form_id}", response_model=FormResponse)
def update_form(
    form_id: str,
    payload: FormPayload,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    item = owned(db, MarketingForm, form_id, user.company_id)
    for key, value in payload.model_dump(mode="json").items():
        setattr(item, key, value)
    item.revision += 1
    db.commit()
    db.refresh(item)
    return item


def validate_campaign_links(db: Session, payload: CampaignPayload, company_id: str) -> None:
    owned(db, MarketingForm, payload.form_id, company_id)
    for model, object_id in (
        (DigitalCard, payload.card_id),
        (Product, payload.product_id),
        (Employee, payload.owner_employee_id),
    ):
        if object_id:
            owned(db, model, object_id, company_id)


@router.get("/tenant/marketing/campaigns", response_model=list[CampaignResponse])
def list_campaigns(
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(
        db.scalars(
            select(Campaign)
            .where(Campaign.company_id == user.company_id)
            .order_by(Campaign.created_at.desc())
        )
    )


@router.post("/tenant/marketing/campaigns", response_model=CampaignResponse, status_code=201)
def create_campaign(
    payload: CampaignPayload,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    validate_campaign_links(db, payload, user.company_id)
    item = Campaign(company_id=user.company_id, **payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("campaign_slug_exists", "Campaign address already exists", 409) from None
    db.refresh(item)
    return item


@router.put("/tenant/marketing/campaigns/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    payload: CampaignPayload,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    item = owned(db, Campaign, campaign_id, user.company_id)
    validate_campaign_links(db, payload, user.company_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("campaign_slug_exists", "Campaign address already exists", 409) from None
    db.refresh(item)
    return item


@router.post("/tenant/marketing/campaigns/{campaign_id}/{action}", response_model=CampaignResponse)
def change_campaign_status(
    campaign_id: str,
    action: str,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    item = owned(db, Campaign, campaign_id, user.company_id)
    if action not in {"publish", "close"}:
        raise AppError("invalid_action", "Invalid campaign action", 422)
    item.status = (
        CampaignStatus.PUBLISHED.value if action == "publish" else CampaignStatus.CLOSED.value
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/public/campaigns/{slug}", response_model=PublicCampaignResponse)
def get_public_campaign(slug: str, db: Annotated[Session, Depends(get_db)]):
    item, form = public_campaign(db, slug)
    remaining = None if item.capacity is None else max(item.capacity - item.submission_count, 0)
    return PublicCampaignResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        channel=item.channel,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        remaining=remaining,
        state=campaign_state(item),
        fields=form.fields,
        privacy_notice=form.privacy_notice,
        success_message=form.success_message,
    )


def validated_values(form: MarketingForm, values: dict[str, str]) -> dict[str, str]:
    definitions = {str(item["key"]): item for item in form.fields}
    if set(values) - set(definitions):
        raise AppError("unknown_form_field", "Submission contains unknown fields", 422)
    cleaned = {key: value.strip() for key, value in values.items()}
    for key, definition in definitions.items():
        value = cleaned.get(key, "")
        if definition.get("required") and not value:
            raise AppError("required_form_field", f"{definition['label']} is required", 422)
        if len(value) > 3000:
            raise AppError("form_value_too_long", f"{definition['label']} is too long", 422)
        if (
            definition.get("type") == "email"
            and value
            and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value)
        ):
            raise AppError("invalid_email", "Email is invalid", 422)
        if definition.get("type") == "select" and value not in definition.get("options", []):
            raise AppError("invalid_option", f"{definition['label']} is invalid", 422)
    if not cleaned.get("contact"):
        raise AppError("contact_required", "Contact is required", 422)
    return cleaned


@router.post(
    "/public/campaigns/{slug}/submissions",
    response_model=PublicSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_campaign(
    slug: str,
    payload: PublicSubmissionRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    campaign, form = public_campaign(db, slug)
    state = campaign_state(campaign)
    if state != "open":
        raise AppError(f"campaign_{state}", f"Campaign is {state.replace('_', ' ')}", 409)
    if payload.website:
        raise AppError("spam_rejected", "Submission was rejected", 422)
    user_agent = request.headers.get("user-agent", "")
    if is_bot_user_agent(user_agent):
        raise AppError("spam_rejected", "Submission was rejected", 422)
    ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()
    recent = (
        db.scalar(
            select(func.count())
            .select_from(CampaignSubmission)
            .where(
                CampaignSubmission.campaign_id == campaign.id,
                CampaignSubmission.ip_hash == ip_hash,
                CampaignSubmission.created_at >= utc_now() - timedelta(minutes=1),
            )
        )
        or 0
    )
    if recent >= 5:
        raise AppError("submission_rate_limited", "Too many submissions, please try later", 429)
    values = validated_values(form, payload.values)
    contact_hash = hashlib.sha256(values["contact"].lower().encode()).hexdigest()
    duplicate = db.scalar(
        select(CampaignSubmission)
        .where(
            CampaignSubmission.campaign_id == campaign.id,
            CampaignSubmission.contact_hash == contact_hash,
            CampaignSubmission.created_at >= utc_now() - timedelta(hours=24),
        )
        .order_by(CampaignSubmission.created_at.desc())
    )
    if duplicate:
        response.status_code = 200
        return PublicSubmissionResponse(
            id=duplicate.id, duplicate=True, message="请勿重复报名，我们已收到您的信息"
        )
    channel = payload.source or campaign.channel
    item = CampaignSubmission(
        company_id=campaign.company_id,
        campaign_id=campaign.id,
        form_revision=form.revision,
        form_snapshot={
            "name": form.name,
            "fields": form.fields,
            "privacy_notice": form.privacy_notice,
        },
        values=values,
        contact_hash=contact_hash,
        ip_hash=ip_hash,
        channel=channel,
        privacy_agreed=True,
    )
    db.add(item)
    campaign.submission_count += 1
    db.flush()
    employee = db.get(Employee, campaign.owner_employee_id) if campaign.owner_employee_id else None
    add_business_event(
        db,
        company_id=campaign.company_id,
        employee=employee,
        card_id=campaign.card_id,
        product_id=campaign.product_id,
        event_type="campaign_submitted",
        category="lead",
        channel=channel,
        visitor_hash=contact_hash,
        dedupe_key=f"campaign:{item.id}:submitted",
        details={"campaign_id": campaign.id, "submission_id": item.id},
    )
    db.commit()
    return PublicSubmissionResponse(id=item.id, duplicate=False, message=form.success_message)


@router.get("/tenant/marketing/campaigns/{campaign_id}/submissions", response_model=SubmissionPage)
def list_submissions(
    campaign_id: str,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_READ))],
    db: Annotated[Session, Depends(get_db)],
    submission_status: Annotated[SubmissionStatus | None, Query(alias="status")] = None,
):
    owned(db, Campaign, campaign_id, user.company_id)
    conditions = [
        CampaignSubmission.campaign_id == campaign_id,
        CampaignSubmission.company_id == user.company_id,
    ]
    if submission_status:
        conditions.append(CampaignSubmission.status == submission_status.value)
    return SubmissionPage(
        items=list(
            db.scalars(
                select(CampaignSubmission)
                .where(*conditions)
                .order_by(CampaignSubmission.created_at.desc())
            )
        ),
        total=db.scalar(select(func.count()).select_from(CampaignSubmission).where(*conditions))
        or 0,
    )


@router.post("/tenant/marketing/submissions/{submission_id}/convert", response_model=dict)
def convert_submission(
    submission_id: str,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    item = owned(db, CampaignSubmission, submission_id, user.company_id)
    if item.lead_id:
        return {"lead_id": item.lead_id}
    campaign = db.get(Campaign, item.campaign_id)
    if campaign is None or not campaign.card_id or not campaign.owner_employee_id:
        raise AppError(
            "campaign_lead_binding_required", "Bind a card and owner before converting", 409
        )
    contact = str(item.values.get("contact", ""))
    name = str(item.values.get("name", "活动报名"))
    lead = Lead(
        company_id=item.company_id,
        card_id=campaign.card_id,
        product_id=campaign.product_id,
        owner_employee_id=campaign.owner_employee_id,
        assigned_employee_id=campaign.owner_employee_id,
        name=name,
        contact=contact,
        normalized_contact=contact.strip().lower(),
        demand=str(item.values.get("demand", item.values.get("message", ""))) or None,
        source=item.channel,
        privacy_agreed=True,
        status=LeadStatus.ASSIGNED.value,
    )
    db.add(lead)
    db.flush()
    item.lead_id = lead.id
    item.status = SubmissionStatus.CONVERTED.value
    db.commit()
    return {"lead_id": lead.id}


@router.post("/tenant/marketing/submissions/{submission_id}/invalid", response_model=dict)
def invalidate_submission(
    submission_id: str,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    item = owned(db, CampaignSubmission, submission_id, user.company_id)
    if item.lead_id:
        raise AppError(
            "submission_already_converted", "Converted submission cannot be invalidated", 409
        )
    item.status = SubmissionStatus.INVALID.value
    db.commit()
    return {"status": item.status}


@router.get("/tenant/marketing/campaigns/{campaign_id}/stats", response_model=CampaignStats)
def campaign_stats(
    campaign_id: str,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    campaign = owned(db, Campaign, campaign_id, user.company_id)
    rows = db.execute(
        select(CampaignSubmission.status, CampaignSubmission.channel, func.count())
        .where(CampaignSubmission.campaign_id == campaign.id)
        .group_by(CampaignSubmission.status, CampaignSubmission.channel)
    ).all()
    converted = sum(count for state, _, count in rows if state == SubmissionStatus.CONVERTED.value)
    invalid = sum(count for state, _, count in rows if state == SubmissionStatus.INVALID.value)
    channels: dict[str, int] = {}
    for _, channel, count in rows:
        channels[channel] = channels.get(channel, 0) + count
    return CampaignStats(
        submissions=campaign.submission_count,
        converted=converted,
        invalid=invalid,
        conversion_rate=round(converted / campaign.submission_count, 4)
        if campaign.submission_count
        else 0,
        channels=channels,
    )


@router.get("/tenant/marketing/campaigns/{campaign_id}/export")
def export_submissions(
    campaign_id: str,
    user: Annotated[User, Depends(require_permission(Permission.MARKETING_EXPORT))],
    db: Annotated[Session, Depends(get_db)],
):
    campaign = owned(db, Campaign, campaign_id, user.company_id)
    items = db.scalars(
        select(CampaignSubmission)
        .where(CampaignSubmission.campaign_id == campaign.id)
        .order_by(CampaignSubmission.created_at)
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "status", "channel", "values", "lead_id", "created_at"])
    for item in items:
        writer.writerow(
            [
                item.id,
                item.status,
                item.channel,
                "; ".join(f"{key}={value}" for key, value in item.values.items()),
                item.lead_id or "",
                item.created_at.isoformat(),
            ]
        )
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="campaign-{campaign.id}.csv"'},
    )
