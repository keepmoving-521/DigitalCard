from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from digitalcard.core.time import utc_now
from digitalcard.db.base import Base


class LeadStatus(StrEnum):
    NEW = "new"
    ASSIGNED = "assigned"
    CLAIMED = "claimed"
    CONTACTED = "contacted"
    INVALID = "invalid"
    CONVERTED = "converted"


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_company_assignee", "company_id", "assigned_employee_id"),
        Index("ix_leads_company_status", "company_id", "status"),
        Index("ix_leads_company_contact", "company_id", "normalized_contact"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    card_id: Mapped[str] = mapped_column(ForeignKey("digital_cards.id", ondelete="CASCADE"))
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    owner_employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    assigned_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    converted_customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100))
    contact: Mapped[str] = mapped_column(String(320))
    normalized_contact: Mapped[str] = mapped_column(String(320))
    demand: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="direct")
    privacy_agreed: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(32), default=LeadStatus.ASSIGNED.value)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    last_submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(String(500))
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
