export type LeadStatus = 'new' | 'assigned' | 'claimed' | 'contacted' | 'invalid' | 'converted'

export interface Lead {
  id: string; card_id: string; product_id: string | null; owner_employee_id: string
  assigned_employee_id: string | null; name: string; contact: string; demand: string | null
  source: string; status: LeadStatus; duplicate_count: number; last_submitted_at: string
  claimed_at: string | null; created_at: string; updated_at: string
}
export interface LeadPage { items: Lead[]; total: number; offset: number; limit: number }
export interface NotificationItem { id: string; kind: string; title: string; content: string; related_type: string | null; related_id: string | null; read_at: string | null; created_at: string }
export interface NotificationPage { items: NotificationItem[]; unread_count: number }
