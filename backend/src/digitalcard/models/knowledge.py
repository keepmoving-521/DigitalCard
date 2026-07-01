from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from digitalcard.core.time import utc_now
from digitalcard.db.base import Base


class KnowledgeStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    DISABLED = "disabled"
    FAILED = "failed"


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        Index("ix_knowledge_company_status", "company_id", "status"),
        Index("ix_knowledge_company_type_source", "company_id", "source_type", "source_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default=KnowledgeStatus.PENDING.value)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class AiConfiguration(Base):
    __tablename__ = "ai_configurations"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    public_qa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sales_assistant_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_message: Mapped[str] = mapped_column(String(500), default="您好，我是企业 AI 助手")
    system_prompt: Mapped[str] = mapped_column(
        String(2000), default="仅根据已授权企业知识回答，不确定时转人工。"
    )
    daily_limit: Mapped[int] = mapped_column(Integer, default=100)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class AiInteraction(Base):
    __tablename__ = "ai_interactions"
    __table_args__ = (Index("ix_ai_interactions_company_time", "company_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(32))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
