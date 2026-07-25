import { describe, expect, it, vi } from 'vitest'

import { pathsApi } from '@/api/paths'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json'
    }
  })
}

describe('pathsApi', () => {
  it('creates path with parent directory payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        path_id: 'path_1',
        parent_path_id: 'root',
        path_name: 'Archive',
        path_type: 'normal',
        path_level: 1,
        sort_index: 1,
        full_path: '/Archive',
        description: null,
        is_hidden: false,
        status: 'active',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      }, 201)
    )
    vi.stubGlobal('fetch', fetchMock)

    await pathsApi.createPath({
      path_name: 'Archive',
      parent_path_id: 'root',
      path_type: 'normal',
      description: null,
      is_hidden: false
    })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/paths')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toMatchObject({
      path_name: 'Archive',
      parent_path_id: 'root'
    })
  })

  it('moves and deletes path through directory endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          path_id: 'path_1',
          parent_path_id: 'path_2',
          path_name: 'Archive',
          path_type: 'normal',
          path_level: 2,
          sort_index: 1,
          full_path: '/Target/Archive',
          description: null,
          is_hidden: false,
          status: 'active',
          created_at: '2026-07-24T00:00:00',
          updated_at: '2026-07-24T00:00:00'
        })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await pathsApi.movePath('path_1', 'path_2')
    await pathsApi.deletePath('path_1')

    const moveInit = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/paths/path_1/move')
    expect(moveInit.method).toBe('PATCH')
    expect(JSON.parse(moveInit.body as string)).toEqual({ parent_path_id: 'path_2' })
    expect(String(fetchMock.mock.calls[1][0])).toContain('/api/paths/path_1')
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe('DELETE')
  })

  it('updates path metadata through PATCH endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        path_id: 'path_1',
        parent_path_id: 'root',
        path_name: 'Archive',
        path_type: 'normal',
        path_level: 1,
        sort_index: 1,
        full_path: '/Archive',
        description: 'done',
        is_hidden: true,
        status: 'active',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await pathsApi.updatePath('path_1', {
      path_name: 'Archive',
      description: 'done',
      is_hidden: true
    })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/paths/path_1')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({
      path_name: 'Archive',
      description: 'done',
      is_hidden: true
    })
  })
})
