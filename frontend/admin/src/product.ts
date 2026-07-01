export interface Material {
  id: string
  company_id: string
  name: string
  kind: 'image' | 'video' | 'pdf'
  mime_type: string
  size_bytes: number
  access: 'public' | 'private'
  created_at: string
  updated_at: string
}

export interface ProductCategory {
  id: string
  company_id: string
  code: string
  name: string
  sort_order: number
  is_active: boolean
}

export interface Product {
  id: string
  company_id: string
  category_id: string | null
  name: string
  summary: string | null
  description: string | null
  specifications: Record<string, string>
  cover_material_id: string | null
  video_material_id: string | null
  gallery_material_ids: string[]
  attachment_material_ids: string[]
  video_url: string | null
  status: 'draft' | 'published' | 'offline'
  sort_order: number
}

export interface ProductPage { items: Product[]; total: number; offset: number; limit: number }
