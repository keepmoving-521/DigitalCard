export interface Customer { id: string; company_id: string; owner_employee_id: string; name: string; primary_contact: string; tags: string[]; status: 'active' | 'archived' | 'merged'; merged_into_id: string | null; archived_at: string | null; created_at: string; updated_at: string }
export interface Contact { id: string; name: string; contact_type: string; contact_value: string; position: string | null; is_primary: boolean; sort_order: number; created_at: string }
export interface CustomerDetail extends Customer { contacts: Contact[] }
export interface CustomerPage { items: Customer[]; total: number; offset: number; limit: number }
export interface FollowUp { id: string; customer_id: string; method: string; content: string; occurred_at: string; next_follow_up_at: string | null; created_at: string }
export interface TimelineEvent { id: string; event_type: string; title: string; details: Record<string, unknown>; actor_user_id: string | null; occurred_at: string }
export interface Stage { id: string; code: string; name: string; sort_order: number; probability: number; is_won: boolean; is_lost: boolean; is_active: boolean }
export interface Opportunity { id: string; customer_id: string; owner_employee_id: string; stage_id: string; title: string; expected_amount: string; expected_close_date: string | null; created_at: string; updated_at: string }
export interface Funnel { items: Array<{ stage_id: string; stage_name: string; count: number; expected_amount: string }> }
export interface MergePreview { target_customer_id: string; source_customer_id: string; conflicts: Record<string, string[]>; moved_counts: Record<string, number> }
