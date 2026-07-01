from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from digitalcard.core.time import utc_now
from digitalcard.db.base import Base


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class SubmissionStatus(StrEnum):
    SUBMITTED = "submitted"
    CONVERTED = "converted"
    INVALID = "invalid"


class MarketingForm(Base):
    __tablename__ = "marketing_forms"
    __table_args__ = (Index("ix_marketing_forms_company_active", "company_id", "is_active"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    fields: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    privacy_notice: Mapped[str] = mapped_column(Text)
    success_message: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("ix_campaigns_company_status", "company_id", "status"),
        Index("ix_campaigns_time", "starts_at", "ends_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    form_id: Mapped[str] = mapped_column(ForeignKey("marketing_forms.id", ondelete="RESTRICT"))
    card_id: Mapped[str | None] = mapped_column(
        ForeignKey("digital_cards.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    owner_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(String(64), default="direct")
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=CampaignStatus.DRAFT.value)
    submission_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class CampaignSubmission(Base):
    __tablename__ = "campaign_submissions"
    __table_args__ = (
        Index("ix_campaign_submissions_campaign_time", "campaign_id", "created_at"),
        Index("ix_campaign_submissions_company_status", "company_id", "status"),
        Index("ix_campaign_submissions_contact", "campaign_id", "contact_hash"),
        Index("ix_campaign_submissions_ip_time", "campaign_id", "ip_hash", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    lead_id: Mapped[str | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    form_revision: Mapped[int] = mapped_column(Integer)
    form_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    values: Mapped[dict[str, object]] = mapped_column(JSON)
    contact_hash: Mapped[str] = mapped_column(String(64))
    ip_hash: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(64))
    privacy_agreed: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(32), default=SubmissionStatus.SUBMITTED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
