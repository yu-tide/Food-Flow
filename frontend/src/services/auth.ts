import { apiPost } from './api'
import type { AuthUser, LoginResponse, RegisterRequest, SendCodeRequest } from '@/types/auth'

type SendCodeResult = {
  message: string
  dev_code?: string
}

export async function sendRegisterCode(phone: string): Promise<SendCodeResult> {
  const body: SendCodeRequest = { phone, scene: 'register' }
  return apiPost<SendCodeResult>('/api/auth/send-code', body)
}

export async function register(data: RegisterRequest): Promise<{ message: string; user: AuthUser }> {
  return apiPost('/api/auth/register', data)
}

export async function login(data: { phone: string; password: string }): Promise<LoginResponse> {
  return apiPost<LoginResponse>('/api/auth/login', data)
}

export function logout(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export function saveAuth(response: LoginResponse): void {
  if (typeof window === 'undefined') return
  localStorage.setItem('token', response.access_token)
  localStorage.setItem('user', JSON.stringify(response.user))
}
