import { reactive } from 'vue'

export type UserRole = 'admin' | 'user'

export interface User {
  id: string
  email: string
  display_name: string
  role: UserRole
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

interface SessionResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

interface ErrorResponse {
  error?: { code?: string; message?: string }
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message)
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const authState = reactive<{
  user: User | null
  accessToken: string | null
  initialized: boolean
}>({
  user: null,
  accessToken: null,
  initialized: false,
})

async function parseError(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => ({}))) as ErrorResponse
  return new ApiError(
    response.status,
    body.error?.code ?? 'request_failed',
    body.error?.message ?? '请求失败，请稍后重试',
  )
}

async function rawRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  })
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function applySession(session: SessionResponse): void {
  authState.accessToken = session.access_token
  authState.user = session.user
}

export async function login(email: string, password: string): Promise<User> {
  const session = await rawRequest<SessionResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  applySession(session)
  return session.user
}

export async function refreshSession(): Promise<User> {
  const session = await rawRequest<SessionResponse>('/auth/refresh', { method: 'POST' })
  applySession(session)
  return session.user
}

export async function initializeAuth(): Promise<void> {
  if (authState.initialized) return
  try {
    await refreshSession()
  } catch {
    authState.user = null
    authState.accessToken = null
  } finally {
    authState.initialized = true
  }
}

export async function logout(): Promise<void> {
  try {
    await rawRequest<void>('/auth/logout', { method: 'POST' })
  } finally {
    authState.user = null
    authState.accessToken = null
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const execute = () =>
    rawRequest<T>(path, {
      ...init,
      headers: {
        ...init.headers,
        ...(authState.accessToken
          ? { Authorization: `Bearer ${authState.accessToken}` }
          : {}),
      },
    })
  try {
    return await execute()
  } catch (error) {
    if (retry && error instanceof ApiError && error.status === 401) {
      await refreshSession()
      return apiRequest<T>(path, init, false)
    }
    throw error
  }
}

