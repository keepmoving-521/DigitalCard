export interface OnboardingStatus { completed: boolean; completed_count: number; total_count: number; steps: Array<{ code: string; name: string; completed: boolean; path: string }> }
export interface RateMetric { attempts: number; successes: number; success_rate: number | null }
export interface Monitoring { requests: number; errors: number; error_rate: number; p95_duration_ms: number; card_publish: RateMetric; public_card: RateMetric; lead_submit: RateMetric; average_first_response_minutes: number | null }
