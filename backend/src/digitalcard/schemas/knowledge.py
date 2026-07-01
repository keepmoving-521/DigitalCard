from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from digitalcard.models.knowledge import KnowledgeStatus


class AiConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    public_qa_enabled: bool = False
    sales_assistant_enabled: bool = False
    welcome_message: str = Field(default="您好，我是企业 AI 助手", max_length=500)
    system_prompt: str = Field(
        default="仅根据已授权企业知识回答，不确定时转人工。", max_length=2000
    )
    daily_limit: int = Field(default=100, ge=1, le=100_000)


class AiConfigResponse(AiConfigPayload):
    model_config = ConfigDict(from_attributes=True)
    company_id: str
    updated_at: datetime


class KnowledgeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: Literal["faq", "case", "document"]
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)
    is_authorized: bool = True


class KnowledgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_type: str
    source_id: str | None
    title: str
    content: str
    is_authorized: bool
    status: KnowledgeStatus
    error_message: str | None
    indexed_at: datetime | None
    updated_at: datetime


class PublicAiQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=1000)
    visitor_id: str | None = Field(default=None, max_length=100)


class AiCitation(BaseModel):
    source_id: str
    source_type: str
    title: str
    excerpt: str


class AiAnswer(BaseModel):
    interaction_id: str
    answer: str
    uncertain: bool
    citations: list[AiCitation]
    handoff_url: str | None
    suggestion_notice: str = "AI 内容仅供参考，请以企业人员确认为准。"


class AiFeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=500)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_type: Literal["company_intro", "product_copy", "follow_up_suggestion"]
    product_id: str | None = None
    context: str | None = Field(default=None, max_length=5000)


class DraftResponse(BaseModel):
    interaction_id: str
    content: str
    requires_confirmation: bool = True
    notice: str = "这是 AI 建议草稿，人工确认后才能使用或发布。"


class AiStats(BaseModel):
    calls: int
    successes: int
    failures: int
    uncertain: int
    positive_feedback: int
    negative_feedback: int
    failure_rate: float
