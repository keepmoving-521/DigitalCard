from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from digitalcard.core.time import utc_now
from digitalcard.db.base import Base


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    MERGED = "merged"


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_company_owner", "company_id", "owner_employee_id"),
        Index("ix_customers_company_status", "company_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    owner_employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(160))
    primary_contact: Mapped[str] = mapped_column(String(320))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default=CustomerStatus.ACTIVE.value)
    merged_into_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class CustomerContact(Base):
    __tablename__ = "customer_contacts"
    __table_args__ = (Index("ix_customer_contacts_customer", "customer_id", "sort_order"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    contact_type: Mapped[str] = mapped_column(String(32))
    contact_value: Mapped[str] = mapped_column(String(320))
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class FollowUp(Base):
    __tablename__ = "follow_ups"
    __table_args__ = (Index("ix_follow_ups_customer_occurred", "customer_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    method: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CustomerEvent(Base):
    __tablename__ = "customer_events"
    __table_args__ = (Index("ix_customer_events_customer_occurred", "customer_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class OpportunityStage(Base):
    __tablename__ = "opportunity_stages"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_opportunity_stages_company_code"),
        Index("ix_opportunity_stages_company_sort", "company_id", "sort_order"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    probability: Mapped[int] = mapped_column(Integer, default=0)
    is_won: Mapped[bool] = mapped_column(Boolean, default=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        Index("ix_opportunities_company_stage", "company_id", "stage_id"),
        Index("ix_opportunities_customer", "customer_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    owner_employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    stage_id: Mapped[str] = mapped_column(ForeignKey("opportunity_stages.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class OpportunityStageHistory(Base):
    __tablename__ = "opportunity_stage_history"
    __table_args__ = (Index("ix_opportunity_history_opportunity", "opportunity_id", "changed_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    from_stage_id: Mapped[str | None] = mapped_column(
        ForeignKey("opportunity_stages.id", ondelete="SET NULL"), nullable=True
    )
    to_stage_id: Mapped[str] = mapped_column(
        ForeignKey("opportunity_stages.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
