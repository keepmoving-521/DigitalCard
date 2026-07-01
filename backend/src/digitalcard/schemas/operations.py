from pydantic import BaseModel


class OnboardingStep(BaseModel):
    code: str
    name: str
    completed: bool
    path: str


class OnboardingResponse(BaseModel):
    completed: bool
    completed_count: int
    total_count: int
    steps: list[OnboardingStep]


class RateMetric(BaseModel):
    attempts: int
    successes: int
    success_rate: float | None


class MonitoringResponse(BaseModel):
    requests: int
    errors: int
    error_rate: float
    p95_duration_ms: float
    card_publish: RateMetric
    public_card: RateMetric
    lead_submit: RateMetric
    average_first_response_minutes: float | None
