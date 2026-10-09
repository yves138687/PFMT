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
  it('uploads files with a conflict strategy', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          file_id: 'file_1',
          path_id: 'root',
          original_name: 'note(1).txt',
          file_type: 'text',
          size_bytes: 5,
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

    await filesApi.uploadFile({
      file: new File(['hello'], 'note.txt', { type: 'text/plain' }),
      pathId: 'root',
      encryptionEnabled: true,
      conflictStrategy: 'rename'
    })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    const body = init.body as FormData
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/upload')
    expect(init.method).toBe('POST')
    expect(body.get('path_id')).toBe('root')
    expect(body.get('conflict_strategy')).toBe('rename')
  })

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

    await filesApi.getFileDetail('file_1')

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

    await filesApi.updateFileRemark('file_1', '备注')

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
      }
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

    await filesApi.searchFiles('alpha')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/search?q=alpha&limit=50')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('GET')
  })

  it('reads dashboard summary without visibility query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        file_total: 2,
        path_total: 1,
        markdown_total: 1,
        recent_accessed: []
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.getDashboardSummary()

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/dashboard')
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

    await filesApi.updateFileTags('file_1', ['work'])
    await filesApi.getPreviewBlob('file_1')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/tags')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({ tag_names: ['work'] })
    expect(String(fetchMock.mock.calls[1][0])).toContain('/api/files/file_1/preview')
    expect(String(fetchMock.mock.calls[1][0])).not.toContain('show_hidden')
  })

  it('requests tag suggestions through the file endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            tag_name: '知识图谱',
            score: 1001,
            source: 'existing_tag_match',
            existing_tag_id: 'tag_1',
            matched_count: 3
          }
        ]
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.suggestFileTags('file_1')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/tag-suggestions?limit=80')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST')
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

    await filesApi.getMarkdownFile('file_1')

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

    await filesApi.getTextFile('file_1')

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

    await filesApi.issuePreviewToken('file_1')

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

    await filesApi.getDocument('file_1')
    await filesApi.saveDocument('file_1', { document_format: 'markdown', content: '# Saved' })
    await filesApi.convertDocument('file_1', { target_format: 'html', target_name: 'note.html' })
    await filesApi.mergeDocuments(
      {
        file_ids: ['file_1', 'file_2'],
        target_format: 'markdown',
        target_name: 'merged.md'
      }
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

    await filesApi.moveFile('file_1', 'path_2')

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1/move')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ path_id: 'path_2' })
  })

  it('deletes file without visibility query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.deleteFile('file_1')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/file_1')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE')
  })

  it('deletes selected files through the batch endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.deleteFiles(['file_1', 'file_2'])

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/files/delete')
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('show_hidden')
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST')
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({
      file_ids: ['file_1', 'file_2']
    })
  })

  it('exports one file and selected files without visibility query', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('single-export', { status: 200 }))
      .mockResolvedValueOnce(new Response('batch-export', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await filesApi.exportFile('file_1')
    await filesApi.exportFiles(['file_1', 'file_2'])

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

  it('manages tags through the tags API', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([{ tag_id: 'tag_1', tag_name: 'work', file_count: 2 }]))
      .mockResolvedValueOnce(jsonResponse({ items: [], total: 0 }))
      .mockResolvedValueOnce(jsonResponse({ tag_id: 'tag_1', tag_name: 'archive', tag_color: '#3366ff', file_count: 2 }))
      .mockResolvedValueOnce(
        jsonResponse({
          created: [{ tag_id: 'tag_2', tag_name: 'alpha' }],
          reused: [{ tag_id: 'tag_1', tag_name: 'archive' }],
          invalid: [],
          total_created: 1,
          total_reused: 1,
          total_invalid: 0
        })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await tagsApi.listTags({ withUsage: true, includeUnused: true })
    await tagsApi.listTagFiles('tag_1')
    await tagsApi.updateTag('tag_1', { tag_name: 'archive', tag_color: '#3366ff' })
    await tagsApi.importTags({ raw_text: 'archive，alpha', delimiter: 'comma_cn' })
    await tagsApi.deleteTag('tag_1')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/tags?with_usage=true&include_unused=true')
    expect(String(fetchMock.mock.calls[1][0])).toContain('/api/tags/tag_1/files')
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe('PATCH')
    expect(JSON.parse((fetchMock.mock.calls[2][1] as RequestInit).body as string)).toEqual({
      tag_name: 'archive',
      tag_color: '#3366ff'
    })
    expect(String(fetchMock.mock.calls[3][0])).toContain('/api/tags/import')
    expect((fetchMock.mock.calls[3][1] as RequestInit).method).toBe('POST')
    expect(JSON.parse((fetchMock.mock.calls[3][1] as RequestInit).body as string)).toEqual({
      raw_text: 'archive，alpha',
      delimiter: 'comma_cn'
    })
    expect(String(fetchMock.mock.calls[4][0])).toContain('/api/tags/tag_1')
    expect((fetchMock.mock.calls[4][1] as RequestInit).method).toBe('DELETE')
  })
})
