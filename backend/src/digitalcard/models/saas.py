from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from digitalcard.core.time import utc_now
from digitalcard.db.base import Base


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"


class SaasPlan(Base):
    __tablename__ = "saas_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    employee_limit: Mapped[int] = mapped_column(Integer)
    card_limit: Mapped[int] = mapped_column(Integer)
    storage_limit_bytes: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    plan_id: Mapped[str] = mapped_column(ForeignKey("saas_plans.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(32), default=SubscriptionStatus.TRIAL.value)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_cleanup_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class SubscriptionRenewal(Base):
    __tablename__ = "subscription_renewals"
    __table_args__ = (Index("ix_subscription_renewals_company_time", "company_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    plan_id: Mapped[str] = mapped_column(ForeignKey("saas_plans.id", ondelete="RESTRICT"))
    previous_expires_at: Mapped[datetime] = mapped_column(DateTime)
    new_expires_at: Mapped[datetime] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PlatformOperationLog(Base):
    __tablename__ = "platform_operation_logs"
    __table_args__ = (Index("ix_platform_logs_company_time", "company_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class TenantSupportGrant(Base):
    __tablename__ = "tenant_support_grants"
    __table_args__ = (Index("ix_support_grants_company_expiry", "company_id", "expires_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    granted_to_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    granted_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    reason: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
