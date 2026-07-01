from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.api.dependencies import require_permission
from digitalcard.core.config import Settings, get_settings
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.db.session import get_db
from digitalcard.models.account import User
from digitalcard.models.card import DigitalCard
from digitalcard.models.crm import Customer
from digitalcard.models.employee import Employee
from digitalcard.models.lead import Lead, LeadStatus
from digitalcard.models.open_platform import (
    OpenApiCallLog,
    OpenApplication,
    OpenIdempotency,
    WebhookDelivery,
    WebhookSubscription,
)
from digitalcard.schemas.open_platform import (
    OPEN_SCOPES,
    WEBHOOK_EVENTS,
    ApplicationCredentialResponse,
    ApplicationPayload,
    ApplicationResponse,
    ApplicationStatusPayload,
    OpenCustomerUpdate,
    OpenLeadRequest,
    WebhookCredentialResponse,
    WebhookPayload,
    WebhookResponse,
)
from digitalcard.services.open_platform import (
    authenticate_application,
    deliver_webhook,
    enqueue_webhooks,
    log_call,
    new_secret,
    require_scope,
    secret_hash,
    webhook_secret,
)
from digitalcard.services.permissions import Permission

router = APIRouter(tags=["open platform"])


def tenant_app(db: Session, company_id: str, app_id: str) -> OpenApplication:
    app = db.scalar(
        select(OpenApplication).where(
            OpenApplication.id == app_id, OpenApplication.company_id == company_id
        )
    )
    if app is None:
        raise AppError("open_app_not_found", "Open application was not found", 404)
    return app


def validate_scopes(scopes: list[str]) -> None:
    invalid = set(scopes) - OPEN_SCOPES
    if invalid:
        raise AppError("open_scope_invalid", "One or more scopes are invalid", 422)


@router.get("/tenant/open/apps", response_model=list[ApplicationResponse])
def list_apps(
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(
        db.scalars(select(OpenApplication).where(OpenApplication.company_id == user.company_id))
    )


@router.post("/tenant/open/apps", response_model=ApplicationCredentialResponse, status_code=201)
def create_app(
    payload: ApplicationPayload,
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    validate_scopes(payload.scopes)
    secret = new_secret()
    app = OpenApplication(
        company_id=user.company_id,
        name=payload.name,
        app_key=f"dc_{new_secret()[:20]}",
        secret_hash=secret_hash(secret),
        scopes=sorted(set(payload.scopes)),
        rate_limit_per_minute=payload.rate_limit_per_minute,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    values = ApplicationResponse.model_validate(app, from_attributes=True).model_dump()
    return ApplicationCredentialResponse(**values, app_secret=secret)


@router.post("/tenant/open/apps/{app_id}/rotate", response_model=ApplicationCredentialResponse)
def rotate_app_secret(
    app_id: str,
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    app = tenant_app(db, user.company_id, app_id)
    secret = new_secret()
    app.secret_hash = secret_hash(secret)
    db.commit()
    db.refresh(app)
    values = ApplicationResponse.model_validate(app, from_attributes=True).model_dump()
    return ApplicationCredentialResponse(**values, app_secret=secret)


@router.patch("/tenant/open/apps/{app_id}/status", response_model=ApplicationResponse)
def set_app_status(
    app_id: str,
    payload: ApplicationStatusPayload,
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    app = tenant_app(db, user.company_id, app_id)
    app.is_active = payload.is_active
    db.commit()
    db.refresh(app)
    return app


@router.post(
    "/tenant/open/apps/{app_id}/webhooks",
    response_model=WebhookCredentialResponse,
    status_code=201,
)
def create_webhook(
    app_id: str,
    payload: WebhookPayload,
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    app = tenant_app(db, user.company_id, app_id)
    invalid = set(payload.events) - WEBHOOK_EVENTS
    if invalid:
        raise AppError("webhook_event_invalid", "One or more webhook events are invalid", 422)
    item = WebhookSubscription(
        company_id=user.company_id,
        application_id=app.id,
        target_url=str(payload.target_url),
        events=sorted(set(payload.events)),
    )
    db.add(item)
    db.flush()
    signing_secret = webhook_secret(settings, item.id)
    db.commit()
    db.refresh(item)
    values = WebhookResponse.model_validate(item, from_attributes=True).model_dump()
    return WebhookCredentialResponse(**values, signing_secret=signing_secret)


@router.get("/tenant/open/apps/{app_id}/webhooks", response_model=list[WebhookResponse])
def list_webhooks(
    app_id: str,
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    app = tenant_app(db, user.company_id, app_id)
    return list(
        db.scalars(select(WebhookSubscription).where(WebhookSubscription.application_id == app.id))
    )


@router.get("/tenant/open/logs")
def list_open_logs(
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(
        db.scalars(
            select(OpenApiCallLog)
            .where(OpenApiCallLog.company_id == user.company_id)
            .order_by(OpenApiCallLog.created_at.desc())
            .limit(500)
        )
    )


@router.get("/tenant/open/deliveries")
def list_deliveries(
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(
        db.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.company_id == user.company_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(500)
        )
    )


@router.post("/tenant/open/deliveries/process-due")
def process_due_deliveries(
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    deliveries = list(
        db.scalars(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.company_id == user.company_id,
                WebhookDelivery.status.in_(["pending", "retrying"]),
                WebhookDelivery.next_retry_at <= utc_now(),
            )
            .order_by(WebhookDelivery.next_retry_at)
            .limit(100)
        )
    )
    for delivery in deliveries:
        deliver_webhook(db, delivery)
    db.commit()
    return {
        "processed": len(deliveries),
        "delivered": sum(item.status == "delivered" for item in deliveries),
        "failed": sum(item.status == "failed" for item in deliveries),
    }


@router.post("/tenant/open/deliveries/{delivery_id}/retry")
def retry_delivery(
    delivery_id: str,
    user: Annotated[User, Depends(require_permission(Permission.OPEN_PLATFORM_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    delivery = db.scalar(
        select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id, WebhookDelivery.company_id == user.company_id
        )
    )
    if delivery is None:
        raise AppError("webhook_delivery_not_found", "Webhook delivery was not found", 404)
    delivery.status = "pending"
    delivery.next_retry_at = utc_now()
    deliver_webhook(db, delivery)
    db.commit()
    return {
        "status": delivery.status,
        "attempts": delivery.attempts,
        "error": delivery.error_message,
    }


def open_app(
    db: Annotated[Session, Depends(get_db)],
    app_key: Annotated[str | None, Header(alias="X-App-Key")] = None,
    app_secret: Annotated[str | None, Header(alias="X-App-Secret")] = None,
):
    return authenticate_application(db, app_key, app_secret)


@router.post("/open/v1/leads", status_code=status.HTTP_201_CREATED)
def open_create_lead(
    payload: OpenLeadRequest,
    request: Request,
    app: Annotated[OpenApplication, Depends(open_app)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    require_scope(app, "leads.write")
    previous = db.get(OpenIdempotency, (app.id, payload.idempotency_key))
    if previous:
        log_call(db, app, "POST", request.url.path, 200)
        db.commit()
        return previous.response_data
    card = db.scalar(
        select(DigitalCard).where(
            DigitalCard.id == payload.card_id, DigitalCard.company_id == app.company_id
        )
    )
    if card is None:
        raise AppError("open_card_not_found", "Card was not found", 404)
    owner = db.get(Employee, card.employee_id)
    lead = Lead(
        company_id=app.company_id,
        card_id=card.id,
        product_id=payload.product_id,
        owner_employee_id=owner.id,
        assigned_employee_id=owner.id,
        name=payload.name,
        contact=payload.contact,
        normalized_contact=payload.contact.strip().lower(),
        demand=payload.demand,
        source=payload.source,
        privacy_agreed=True,
        status=LeadStatus.ASSIGNED.value,
    )
    db.add(lead)
    db.flush()
    result = {"id": lead.id, "status": lead.status}
    db.add(
        OpenIdempotency(
            application_id=app.id,
            idempotency_key=payload.idempotency_key,
            response_data=result,
        )
    )
    enqueue_webhooks(db, settings, app.company_id, "lead.created", lead.id, {"lead_id": lead.id})
    log_call(db, app, "POST", request.url.path, 201)
    db.commit()
    return result


@router.patch("/open/v1/customers/{customer_id}")
def open_update_customer(
    customer_id: str,
    payload: OpenCustomerUpdate,
    request: Request,
    app: Annotated[OpenApplication, Depends(open_app)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    require_scope(app, "customers.write")
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.company_id == app.company_id)
    )
    if customer is None:
        raise AppError("open_customer_not_found", "Customer was not found", 404)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    enqueue_webhooks(
        db,
        settings,
        app.company_id,
        "customer.updated",
        customer.id,
        {"customer_id": customer.id},
    )
    log_call(db, app, "PATCH", request.url.path, 200)
    db.commit()
    return {"id": customer.id, "updated": True}


@router.get("/open/v1/customers/{customer_id}")
def open_get_customer(
    customer_id: str,
    request: Request,
    app: Annotated[OpenApplication, Depends(open_app)],
    db: Annotated[Session, Depends(get_db)],
):
    require_scope(app, "customers.read")
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.company_id == app.company_id)
    )
    if customer is None:
        raise AppError("open_customer_not_found", "Customer was not found", 404)
    result = {
        "id": customer.id,
        "name": customer.name,
        "primary_contact": customer.primary_contact,
        "tags": customer.tags,
        "status": customer.status,
        "updated_at": customer.updated_at,
    }
    log_call(db, app, "GET", request.url.path, 200)
    db.commit()
    return result
