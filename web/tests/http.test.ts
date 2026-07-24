import { ElMessage } from 'element-plus'
import { describe, expect, it, vi } from 'vitest'

import { ApiError, registerUnauthorizedHandler, request } from '@/api/http'
import { getAccessToken, setAuthSnapshot } from '@/utils/authStorage'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json'
    }
  })
}

describe('api/http', () => {
  it('adds bearer token and unwraps api envelope data', async () => {
    setAuthSnapshot('token-123', {
      user_id: 'user-1',
      username: 'admin',
      display_name: '管理员',
      status: 'active'
    })

    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ code: 0, data: { ok: true } }))
    vi.stubGlobal('fetch', fetchMock)

    const data = await request<{ ok: boolean }>('/system/settings')

    expect(data.ok).toBe(true)
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer token-123')
  })

  it('clears token and calls unauthorized handler on 401', async () => {
    setAuthSnapshot('stale-token', {
      user_id: 'user-1',
      username: 'admin',
      display_name: '管理员',
      status: 'active'
    })

    const handler = vi.fn()
    registerUnauthorizedHandler(handler)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ message: 'expired' }, 401)))

    await expect(request('/files/tree')).rejects.toBeInstanceOf(ApiError)
    expect(getAccessToken()).toBeNull()
    expect(handler).toHaveBeenCalledTimes(1)
    expect(ElMessage.error).toHaveBeenCalledWith('登录已过期，请重新登录')

    registerUnauthorizedHandler(null)
  })
})
