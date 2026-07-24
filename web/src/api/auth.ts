import { http } from './http'
import type { LoginRequest, LoginResponse, UserProfile } from '@/types/auth'

export const authApi = {
  login(payload: LoginRequest) {
    return http.post<LoginResponse>('/auth/login', payload, { skipAuth: true })
  },
  logout() {
    return http.post<void>('/auth/logout')
  },
  getCurrentUser() {
    return http.get<UserProfile>('/auth/me')
  }
}

export function loginApi(username: string, password: string) {
  return authApi.login({ username, password })
}

export function logoutApi() {
  return authApi.logout()
}

export function meApi() {
  return authApi.getCurrentUser()
}
