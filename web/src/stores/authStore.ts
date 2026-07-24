import type { Router } from 'vue-router'
import { defineStore } from 'pinia'

import { authApi } from '@/api/auth'
import { registerUnauthorizedHandler } from '@/api/http'
import type { LoginRequest, UserProfile } from '@/types/auth'
import { clearAuthSnapshot, getAccessToken, getStoredUser, setAuthSnapshot } from '@/utils/authStorage'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getAccessToken(),
    user: getStoredUser(),
    loading: false
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token)
  },
  actions: {
    async login(payload: LoginRequest) {
      this.loading = true
      try {
        const response = await authApi.login(payload)
        this.token = response.access_token
        this.user = response.user
        setAuthSnapshot(response.access_token, response.user)
      } finally {
        this.loading = false
      }
    },
    async loadCurrentUser() {
      if (!this.token) {
        return null
      }

      const user = await authApi.getCurrentUser()
      this.user = user
      setAuthSnapshot(this.token, user)
      return user
    },
    async logout() {
      try {
        if (this.token) {
          await authApi.logout()
        }
      } finally {
        this.clearAuth()
      }
    },
    clearAuth() {
      this.token = null
      this.user = null
      clearAuthSnapshot()
    },
    setUser(user: UserProfile) {
      this.user = user
      if (this.token) {
        setAuthSnapshot(this.token, user)
      }
    }
  }
})

export function bindAuthUnauthorizedHandler(router: Router) {
  registerUnauthorizedHandler(() => {
    const authStore = useAuthStore()
    authStore.clearAuth()

    const currentPath = router.currentRoute.value.fullPath
    if (router.currentRoute.value.name !== 'login') {
      void router.push({
        name: 'login',
        query: {
          redirect: currentPath
        }
      })
    }
  })
}
