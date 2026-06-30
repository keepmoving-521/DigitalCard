import hashlib
import hmac
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from digitalcard.core.config import Settings
from digitalcard.core.errors import AppError
from digitalcard.core.time import utc_now
from digitalcard.models.account import User, UserRole
from digitalcard.models.employee import Employee, EmployeeInvitation, EmployeeStatus
from digitalcard.models.organization import Company, CompanyStatus, TenantRole
from digitalcard.services.passwords import hash_password, validate_password
from digitalcard.services.tokens import revoke_all_sessions


def invitation_token_hash(token: str, settings: Settings) -> str:
    return hmac.new(
        settings.secret_key.get_secret_value().encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def issue_employee_invitation(
    db: Session,
    employee: Employee,
    role: UserRole,
    settings: Settings,
) -> tuple[EmployeeInvitation, str]:
    if employee.status != EmployeeStatus.ACTIVE.value:
        raise AppError("employee_inactive", "Inactive employees cannot be invited", 409)
    if not employee.email:
        raise AppError("employee_email_required", "An email address is required", 422)
    if role == UserRole.PLATFORM_ADMIN:
        raise AppError("invalid_tenant_role", "A tenant role is required", 422)
    role_exists = db.scalar(
        select(TenantRole.id).where(
            TenantRole.company_id == employee.company_id,
            TenantRole.code == role.value,
        )
    )
    if not role_exists:
        raise AppError("role_not_found", "Role was not found", 404)

    user = db.get(User, employee.user_id) if employee.user_id else None
    email_owner = db.scalar(select(User).where(User.email == employee.email))
    if user is None:
        if email_owner is not None:
            raise AppError("account_email_exists", "This email already has an account", 409)
        user = User(
            email=employee.email,
            display_name=employee.name,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            role=role.value,
            company_id=employee.company_id,
            department_id=employee.department_id,
            is_active=True,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        employee.user_id = user.id
    else:
        if user.company_id != employee.company_id:
            raise AppError("account_tenant_mismatch", "Account belongs to another company", 409)
        if email_owner is not None and email_owner.id != user.id:
            raise AppError("account_email_exists", "This email already has an account", 409)
        if not user.must_change_password:
            raise AppError(
                "account_already_activated", "This account has already been activated", 409
            )
        user.email = employee.email
        user.display_name = employee.name
        user.department_id = employee.department_id
        user.role = role.value
        user.is_active = True

    now = utc_now()
    pending = db.scalars(
        select(EmployeeInvitation).where(
            EmployeeInvitation.employee_id == employee.id,
            EmployeeInvitation.accepted_at.is_(None),
            EmployeeInvitation.revoked_at.is_(None),
        )
    )
    for invitation in pending:
        invitation.revoked_at = now

    raw_token = secrets.token_urlsafe(48)
    invitation = EmployeeInvitation(
        company_id=employee.company_id,
        employee_id=employee.id,
        user_id=user.id,
        token_hash=invitation_token_hash(raw_token, settings),
        expires_at=now + timedelta(hours=settings.invite_expire_hours),
    )
    db.add(invitation)
    db.flush()
    invite_url = f"{settings.invite_base_url}?{urlencode({'token': raw_token})}"
    return invitation, invite_url


def accept_employee_invitation(db: Session, token: str, password: str, settings: Settings) -> User:
    invitation = db.scalar(
        select(EmployeeInvitation).where(
            EmployeeInvitation.token_hash == invitation_token_hash(token, settings)
        )
    )
    now = utc_now()
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= now
    ):
        raise AppError("invitation_invalid", "Invitation is invalid or expired", 400)
    employee = db.get(Employee, invitation.employee_id)
    user = db.get(User, invitation.user_id)
    company = db.get(Company, invitation.company_id)
    if employee is None or user is None or company is None:
        raise AppError("invitation_invalid", "Invitation is invalid or expired", 400)
    if employee.status != EmployeeStatus.ACTIVE.value or not user.is_active:
        raise AppError("employee_inactive", "Employee account is inactive", 403)
    if company.status != CompanyStatus.ACTIVE.value:
        raise AppError("company_suspended", "Company workspace is suspended", 403)
    validate_password(password, user.email)
    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.token_version += 1
    invitation.accepted_at = now
    revoke_all_sessions(db, user.id)
    db.commit()
    return user
