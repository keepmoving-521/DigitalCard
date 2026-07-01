import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from digitalcard.core.config import Settings
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.models.open_platform import (
    OpenApiCallLog,
    OpenApplication,
    WebhookDelivery,
    WebhookSubscription,
)


def secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def webhook_secret(settings: Settings, subscription_id: str) -> str:
    return hmac.new(
        settings.secret_key.get_secret_value().encode(),
        f"webhook:{subscription_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def authenticate_application(
    db: Session, app_key: str | None, app_secret: str | None
) -> OpenApplication:
    if not app_key or not app_secret:
        raise AppError("open_auth_required", "Application credentials are required", 401)
    app = db.scalar(select(OpenApplication).where(OpenApplication.app_key == app_key))
    if (
        app is None
        or not app.is_active
        or not hmac.compare_digest(app.secret_hash, secret_hash(app_secret))
    ):
        raise AppError("open_auth_invalid", "Application credentials are invalid", 401)
    minute_ago = utc_now() - timedelta(minutes=1)
    used = (
        db.scalar(
            select(func.count())
            .select_from(OpenApiCallLog)
            .where(
                OpenApiCallLog.application_id == app.id,
                OpenApiCallLog.created_at >= minute_ago,
            )
        )
        or 0
    )
    if used >= app.rate_limit_per_minute:
        raise AppError("open_rate_limited", "Application rate limit was exceeded", 429)
    app.last_used_at = utc_now()
    return app


def require_scope(app: OpenApplication, scope: str) -> None:
    if scope not in app.scopes:
        raise AppError("open_scope_required", f"Scope {scope} is required", 403)


def log_call(
    db: Session,
    app: OpenApplication,
    method: str,
    path: str,
    status_code: int,
    error_code: str | None = None,
) -> None:
    db.add(
        OpenApiCallLog(
            company_id=app.company_id,
            application_id=app.id,
            method=method,
            path=path,
            status_code=status_code,
            error_code=error_code,
        )
    )


def enqueue_webhooks(
    db: Session,
    settings: Settings,
    company_id: str,
    event_type: str,
    event_id: str,
    data: dict[str, object],
) -> None:
    subscriptions = db.scalars(
        select(WebhookSubscription).where(
            WebhookSubscription.company_id == company_id,
            WebhookSubscription.is_active.is_(True),
        )
    )
    for subscription in subscriptions:
        if event_type not in subscription.events:
            continue
        idempotency_key = f"{subscription.id}:{event_type}:{event_id}"
        if db.scalar(
            select(WebhookDelivery.id).where(WebhookDelivery.idempotency_key == idempotency_key)
        ):
            continue
        payload = {
            "id": event_id,
            "type": event_type,
            "occurred_at": utc_now().isoformat(),
            "data": data,
        }
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            webhook_secret(settings, subscription.id).encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        db.add(
            WebhookDelivery(
                company_id=company_id,
                subscription_id=subscription.id,
                event_type=event_type,
                event_id=event_id,
                idempotency_key=idempotency_key,
                payload=payload,
                signature=signature,
                next_retry_at=utc_now(),
            )
        )


def deliver_webhook(db: Session, delivery: WebhookDelivery) -> None:
    subscription = db.get(WebhookSubscription, delivery.subscription_id)
    if subscription is None or not subscription.is_active:
        delivery.status = "failed"
        delivery.error_message = "Webhook subscription is inactive"
        return
    body = json.dumps(
        delivery.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    request = urllib.request.Request(
        subscription.target_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-DigitalCard-Signature": f"sha256={delivery.signature}",
            "X-DigitalCard-Event": delivery.event_type,
            "Idempotency-Key": delivery.idempotency_key,
        },
    )
    delivery.attempts += 1
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            delivery.response_status = response.status
            if 200 <= response.status < 300:
                delivery.status = "delivered"
                delivery.delivered_at = utc_now()
                delivery.error_message = None
                delivery.next_retry_at = None
                return
            raise RuntimeError(f"HTTP {response.status}")
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        delivery.error_message = str(error)[:1000]
        if delivery.attempts >= 5:
            delivery.status = "failed"
            delivery.next_retry_at = None
        else:
            delivery.status = "retrying"
            delivery.next_retry_at = utc_now() + timedelta(minutes=2**delivery.attempts)
