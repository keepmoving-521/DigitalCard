from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from digitalcard.core.time import utc_now
from digitalcard.db.base import Base


class CardStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    OFFLINE = "offline"


class CardTemplate(Base):
    __tablename__ = "card_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), default="企业默认模板")
    theme_color: Mapped[str] = mapped_column(String(7), default="#1c6a42")
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    module_order: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["profile", "contact", "social", "bio"]
    )
    locked_fields: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["theme_color", "logo_url", "module_order"]
    )
    employee_editable_fields: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: [
            "display_name",
            "headline",
            "avatar_url",
            "bio",
            "phone",
            "email",
            "wechat",
            "website",
            "socials",
        ],
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class DigitalCard(Base):
    __tablename__ = "digital_cards"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", name="uq_digital_cards_company_employee"),
        Index("ix_digital_cards_company_status", "company_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=CardStatus.DRAFT.value, index=True)
    draft_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    published_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    draft_revision: Mapped[int] = mapped_column(Integer, default=1)
    published_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    offline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
