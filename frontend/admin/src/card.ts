export type CardStatus = 'draft' | 'published' | 'offline'

export interface CardTemplate {
  id: string
  company_id: string
  name: string
  theme_color: string
  logo_url: string | null
  module_order: string[]
  locked_fields: string[]
  employee_editable_fields: string[]
  revision: number
  created_at: string
  updated_at: string
}

export interface DigitalCard {
  id: string
  company_id: string
  employee_id: string
  status: CardStatus
  draft_data: Record<string, unknown>
  published_data: Record<string, unknown> | null
  draft_revision: number
  published_revision: number | null
  has_unpublished_changes: boolean
  published_at: string | null
  offline_at: string | null
  created_at: string
  updated_at: string
}

export interface CardPreview {
  card_id: string
  status: CardStatus
  data: Record<string, unknown>
  has_unpublished_changes: boolean
}

export interface SocialLink { platform: string; url: string }
