import re
from datetime import datetime

from sqlalchemy.orm import Session

from digitalcard.models.analytics import BusinessEvent
from digitalcard.models.employee import Employee

BOT_PATTERN = re.compile(
    r"bot|crawler|spider|slurp|headless|preview|facebookexternalhit|bingpreview",
    re.IGNORECASE,
)


def is_bot_user_agent(user_agent: str | None) -> bool:
    return bool(user_agent and BOT_PATTERN.search(user_agent))


def add_business_event(
    db: Session,
    *,
    company_id: str,
    event_type: str,
    category: str,
    dedupe_key: str,
    employee: Employee | None = None,
    card_id: str | None = None,
    product_id: str | None = None,
    lead_id: str | None = None,
    customer_id: str | None = None,
    channel: str = "direct",
    visitor_hash: str | None = None,
    is_bot: bool = False,
    is_internal: bool = False,
    details: dict[str, object] | None = None,
    occurred_at: datetime | None = None,
) -> BusinessEvent:
    event = BusinessEvent(
        company_id=company_id,
        department_id=employee.department_id if employee else None,
        employee_id=employee.id if employee else None,
        card_id=card_id,
        product_id=product_id,
        lead_id=lead_id,
        customer_id=customer_id,
        event_type=event_type,
        event_category=category,
        channel=channel,
        visitor_hash=visitor_hash,
        dedupe_key=dedupe_key,
        is_bot=is_bot,
        is_internal=is_internal,
        details=details or {},
    )
    if occurred_at is not None:
        event.occurred_at = occurred_at
    db.add(event)
    return event
