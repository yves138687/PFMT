import { createMemoryHistory } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { createAppRouter, installRouteGuards } from '@/router'
import { clearAuthSnapshot, setAuthSnapshot } from '@/utils/authStorage'

describe('router guard', () => {
  it('redirects anonymous users to login for business routes', async () => {
    clearAuthSnapshot()
    const router = createAppRouter(createMemoryHistory())
    installRouteGuards(router)

    await router.push('/settings')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/settings')
  })

  it('redirects authenticated users away from login', async () => {
    setAuthSnapshot('token-123', {
      user_id: 'user-1',
      username: 'admin',
      display_name: '管理员',
      status: 'active'
    })

    const router = createAppRouter(createMemoryHistory())
    installRouteGuards(router)

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('dashboard')
  })
})
