import { http } from './http'
import type {
  HiddenContentPasswordRequest,
  HiddenContentPasswordResponse,
  HiddenContentSessionResponse,
  LoginRequest,
  LoginResponse,
  UserProfile
} from '@/types/auth'

export const authApi = {
  login(payload: LoginRequest) {
    return http.post<LoginResponse>('/auth/login', payload, { skipAuth: true })
  },
  logout() {
    return http.post<void>('/auth/logout')
  },
  getCurrentUser() {
    return http.get<UserProfile>('/auth/me')
  },
  getHiddenContentSession() {
    return http.get<HiddenContentSessionResponse>('/auth/hidden-content')
  },
  setHiddenContentSession(enabled: boolean, password?: string) {
    return http.put<HiddenContentSessionResponse>('/auth/hidden-content', { enabled, password })
  },
  changeHiddenContentPassword(currentPassword: string, newPassword: string) {
    const payload: HiddenContentPasswordRequest = {
      current_password: currentPassword.trim() || null,
      new_password: newPassword.trim()
    }
    return http.put<HiddenContentPasswordResponse>('/auth/hidden-content/password', payload)
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
