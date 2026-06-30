export interface Company {
  id: string
  code: string
  name: string
  logo_url: string | null
  description: string | null
  contact_name: string | null
  contact_email: string | null
  contact_phone: string | null
  address: string | null
  status: 'active' | 'suspended'
  created_at: string
  updated_at: string
}

export interface Department {
  id: string
  company_id: string
  code: string
  name: string
  parent_id: string | null
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
  children: Department[]
}

export interface TenantRole {
  id: string
  code: 'company_admin' | 'content_admin' | 'sales' | 'employee'
  name: string
  description: string | null
  is_system: boolean
  permissions: string[]
}

export interface PermissionDefinition {
  code: string
  name: string
  category: string
}

export interface TenantAudit {
  id: string
  company_id: string
  actor_user_id: string | null
  action: string
  target_type: string
  target_id: string
  changes: Record<string, unknown> | null
  created_at: string
}

