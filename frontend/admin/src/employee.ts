export interface Employee {
  id: string
  company_id: string
  employee_no: string
  name: string
  phone: string | null
  email: string | null
  avatar_url: string | null
  bio: string | null
  position: string | null
  department_id: string | null
  manager_id: string | null
  user_id: string | null
  status: 'active' | 'inactive'
  created_at: string
  updated_at: string
}

export interface EmployeePage {
  items: Employee[]
  total: number
  offset: number
  limit: number
}

export interface ImportResult {
  total: number
  succeeded: number
  failed: number
  results: Array<{ row: number; status: string; code: string | null; message: string | null }>
}
