import { describe, expect, it, vi } from 'vitest'

import { filesApi, tagsApi } from '@/api/files'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json'
    }
  })
}

describe('filesApi', () => {
  it('reads file detail without visibility query', async () => {
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
        status: 'active',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.getFileDetail('file_1', true)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
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
        status: 'active',
        remark: '备注',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.updateFileRemark('file_1', '备注', false)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ remark: '备注' })
  })

  it('updates file metadata with PATCH request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_id: 'file_1',
        path_id: 'root',
        original_name: 'renamed.md',
        logical_path: '/renamed.md',
        file_type: 'text',
        size_bytes: 10,
        encryption_enabled: true,
        is_hidden: true,
        status: 'active',
        summary_content: '摘要',
        tags: [],
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.updateFile(
      'file_1',
      {
        original_name: 'renamed.md',
        summary_content: '摘要',
        is_hidden: true
      },
      true
    )

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({
      original_name: 'renamed.md',
      summary_content: '摘要',
      is_hidden: true
    })
  })

  it('searches files by metadata query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ items: [], total: 0 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.searchFiles('alpha', false)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/search?q=alpha&limit=50')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
  })

  it('updates tags and reads preview blob', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          file_id: 'file_1',
          path_id: 'root',
          original_name: 'note.md',
          logical_path: '/note.md',
          file_type: 'text',
          size_bytes: 10,
          encryption_enabled: true,
          is_hidden: false,
          status: 'active',
          tags: [{ tag_id: 'tag_1', tag_name: 'work' }],
          created_at: '2026-07-24T00:00:00',
          updated_at: '2026-07-24T00:00:00'
        })
      )
      .mockResolvedValueOnce(new Response('blob-content', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.updateFileTags('file_1', ['work'], true)
    await filesApi.getPreviewBlob('file_1', true)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/tags')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({ tag_names: ['work'] })
    expect(String(fetchMock.mock.calls[1][0])).toContain('/api/files/file_1/preview')
    expect(String(fetchMock.mock.calls[1][0])).not.toContain('show_hidden')
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

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/markdown')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
  })

  it('reads plain text content through the text endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_id: 'file_1',
        original_name: 'note.txt',
        mime_type: 'text/plain',
        size_bytes: 12,
        content: 'plain text'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.getTextFile('file_1', true)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/text')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
  })

  it('issues short-lived preview token for native media playback', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_id: 'file_1',
        preview_url: '/api/files/file_1/video-stream?token=preview-token',
        expires_at: '2026-07-25T00:05:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.issuePreviewToken('file_1', true)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/preview-token')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST')
  })

  it('creates blank documents through the document endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          file_id: 'file_new',
          path_id: 'root',
          original_name: 'note.md',
          logical_path: '/note.md',
          file_type: 'text',
          size_bytes: 0,
          encryption_enabled: true,
          is_hidden: false,
          status: 'active',
          created_at: '2026-07-24T00:00:00',
          updated_at: '2026-07-24T00:00:00'
        },
        201
      )
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.createDocument({
      path_id: 'root',
      original_name: 'note.md',
      document_format: 'markdown',
      is_hidden: false
    })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/document')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      path_id: 'root',
      original_name: 'note.md',
      document_format: 'markdown',
      is_hidden: false
    })
  })

  it('reads saves and converts unified documents without visibility query', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          file_id: 'file_1',
          original_name: 'note.md',
          mime_type: 'text/markdown',
          size_bytes: 10,
          document_format: 'markdown',
          content: '# Note',
          editable: true,
          rendered_html: '<h1>Note</h1>'
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          file_id: 'file_1',
          original_name: 'note.md',
          mime_type: 'text/markdown',
          size_bytes: 12,
          document_format: 'markdown',
          content: '# Saved',
          editable: true,
          rendered_html: '<h1>Saved</h1>'
        })
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            file_id: 'file_2',
            path_id: 'root',
            original_name: 'note.html',
            logical_path: '/note.html',
            file_type: 'text',
            size_bytes: 18,
            encryption_enabled: true,
            is_hidden: false,
            status: 'active',
            created_at: '2026-07-24T00:00:00',
            updated_at: '2026-07-24T00:00:00'
          },
          201
        )
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            file_id: 'file_3',
            path_id: 'root',
            original_name: 'merged.md',
            logical_path: '/merged.md',
            file_type: 'text',
            size_bytes: 30,
            encryption_enabled: true,
            is_hidden: false,
            status: 'active',
            created_at: '2026-07-24T00:00:00',
            updated_at: '2026-07-24T00:00:00'
          },
          201
        )
      )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.getDocument('file_1', true)
    await filesApi.saveDocument('file_1', { document_format: 'markdown', content: '# Saved' }, true)
    await filesApi.convertDocument('file_1', { target_format: 'html', target_name: 'note.html' }, true)
    await filesApi.mergeDocuments(
      {
        file_ids: ['file_1', 'file_2'],
        target_format: 'markdown',
        target_name: 'merged.md'
      },
      true
    )

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/document')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe('PUT')
    expect(JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string)).toEqual({
      document_format: 'markdown',
      content: '# Saved'
    })
    expect(String(fetchMock.mock.calls[2][0])).toContain('/api/files/file_1/convert')
    expect(String(fetchMock.mock.calls[2][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe('POST')
    expect(JSON.parse((fetchMock.mock.calls[2][1] as RequestInit).body as string)).toEqual({
      target_format: 'html',
      target_name: 'note.html'
    })
    expect(String(fetchMock.mock.calls[3][0])).toContain('/api/files/merge')
    expect(String(fetchMock.mock.calls[3][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[3][1] as RequestInit).method).toBe('POST')
    expect(JSON.parse((fetchMock.mock.calls[3][1] as RequestInit).body as string)).toEqual({
      file_ids: ['file_1', 'file_2'],
      target_format: 'markdown',
      target_name: 'merged.md'
    })
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
        status: 'active',
        created_at: '2026-07-24T00:00:00',
        updated_at: '2026-07-24T00:00:00'
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.moveFile('file_1', 'path_2', true)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/move')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ path_id: 'path_2' })
  })

  it('deletes file without visibility query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.deleteFile('file_1', false)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE')
  })

  it('exports one file and selected files without visibility query', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('single-export', { status: 200 }))
      .mockResolvedValueOnce(new Response('batch-export', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.exportFile('file_1', true)
    await filesApi.exportFiles(['file_1', 'file_2'], true)

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/export')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
    expect(String(fetchMock.mock.calls[1][0])).toContain('/api/files/export')
    expect(String(fetchMock.mock.calls[1][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe('POST')
    expect(JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string)).toEqual({
      file_ids: ['file_1', 'file_2']
    })
  })

  it('creates tags through tags API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ tag_id: 'tag_1', tag_name: 'work' }, 201))
    vi.stubGlobal('fetch', fetchMock)

    await tagsApi.createTag('work')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/tags')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST')
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({
      tag_name: 'work'
    })
  })
})
