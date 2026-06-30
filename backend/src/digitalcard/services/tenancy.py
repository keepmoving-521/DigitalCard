from sqlalchemy.orm import Session

from digitalcard.models.organization import TenantAudit


def record_tenant_audit(
    db: Session,
    company_id: str,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    changes: dict[str, object] | None = None,
) -> None:
    db.add(
        TenantAudit(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            changes=changes,
        )
    )
