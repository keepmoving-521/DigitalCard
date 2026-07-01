from datetime import date, datetime

from pydantic import BaseModel, Field


class AnalyticsMetric(BaseModel):
    views: int
    unique_visitors: int
    shares: int
    clicks: int
    leads: int
    conversions: int
    view_to_lead_rate: float | None
    lead_to_customer_rate: float | None


class TrendPoint(BaseModel):
    date: date
    views: int = 0
    shares: int = 0
    clicks: int = 0
    leads: int = 0
    conversions: int = 0


class RankingItem(BaseModel):
    dimension_id: str
    dimension_name: str
    views: int
    leads: int
    conversions: int


class FunnelItem(BaseModel):
    code: str
    name: str
    value: int
    previous_rate: float | None


class EventSample(BaseModel):
    id: str
    event_type: str
    event_category: str
    employee_id: str | None
    card_id: str | None
    product_id: str | None
    lead_id: str | None
    customer_id: str | None
    channel: str
    occurred_at: datetime


class MetricDefinition(BaseModel):
    code: str
    name: str
    formula: str
    deduplication: str


class AnalyticsDashboardResponse(BaseModel):
    date_from: date
    date_to: date
    scope: str
    metrics: AnalyticsMetric
    trend: list[TrendPoint]
    ranking_dimension: str
    ranking: list[RankingItem]
    funnel: list[FunnelItem]
    samples: list[EventSample]
    definitions: list[MetricDefinition]
    last_updated_at: datetime | None
    filtered_bot_events: int = Field(ge=0)
    filtered_internal_events: int = Field(ge=0)
