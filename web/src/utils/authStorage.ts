import type { UserProfile } from '@/types/auth'

const TOKEN_KEY = 'pfmt.access_token'
const USER_KEY = 'pfmt.user'
const LEGACY_TOKEN_KEY = 'pfmt_access_token'
const LEGACY_USER_KEY = 'pfmt_user'

function canUseStorage() {
  return typeof window !== 'undefined' && Boolean(window.localStorage)
}

export function getAccessToken() {
  if (!canUseStorage()) {
    return null
  }

  return window.localStorage.getItem(TOKEN_KEY) ?? window.localStorage.getItem(LEGACY_TOKEN_KEY)
}

export function getStoredUser(): UserProfile | null {
  if (!canUseStorage()) {
    return null
  }

  const raw = window.localStorage.getItem(USER_KEY) ?? window.localStorage.getItem(LEGACY_USER_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as UserProfile
  } catch {
    clearAuthSnapshot()
    return null
  }
}

export function setAuthSnapshot(token: string, user: UserProfile) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(TOKEN_KEY, token)
  window.localStorage.setItem(USER_KEY, JSON.stringify(user))
  window.localStorage.setItem(LEGACY_TOKEN_KEY, token)
  window.localStorage.setItem(LEGACY_USER_KEY, JSON.stringify(user))
}

export function clearAuthSnapshot() {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.removeItem(TOKEN_KEY)
  window.localStorage.removeItem(USER_KEY)
  window.localStorage.removeItem(LEGACY_TOKEN_KEY)
  window.localStorage.removeItem(LEGACY_USER_KEY)
}

export function hasAuthToken() {
  return Boolean(getAccessToken())
}
