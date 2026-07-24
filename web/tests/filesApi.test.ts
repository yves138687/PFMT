import { describe, expect, it, vi } from 'vitest'

import { filesApi } from '@/api/files'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json'
    }
  })
}

describe('filesApi', () => {
  it('reads file detail with show_hidden query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_id: 'file_1',
        path_id: 'root',
        original_name: 'note.md',
        logical_path: '/note.md',
        file_type: 'text',
        size_bytes: 10,
        encryption_enabled: true,
        is_hidden: false,
        visibility_type: 'normal',
        status: 'active',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.getFileDetail('file_1', true)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1?show_hidden=true')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
  })

  it('updates remark with PATCH request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_id: 'file_1',
        path_id: 'root',
        original_name: 'note.md',
        logical_path: '/note.md',
        file_type: 'text',
        size_bytes: 10,
        encryption_enabled: true,
        is_hidden: false,
        visibility_type: 'normal',
        status: 'active',
        remark: '备注',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.updateFileRemark('file_1', '备注', false)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1?show_hidden=false')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ remark: '备注' })
  })

  it('reads markdown content without manual follow-up action', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_id: 'file_1',
        original_name: 'note.md',
        mime_type: 'text/markdown',
        size_bytes: 10,
        content: '# Note'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.getMarkdownFile('file_1', true)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/markdown?show_hidden=true')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
  })

  it('moves file with target path body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_id: 'file_1',
        path_id: 'path_2',
        original_name: 'note.md',
        logical_path: '/Archive/note.md',
        file_type: 'text',
        size_bytes: 10,
        encryption_enabled: true,
        is_hidden: false,
        visibility_type: 'normal',
        status: 'active',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.moveFile('file_1', 'path_2', true)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/move?show_hidden=true')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ path_id: 'path_2' })
  })

  it('deletes file with show_hidden query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.deleteFile('file_1', false)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1?show_hidden=false')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE')
  })
})
