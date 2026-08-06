import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/files', () => ({
  filesApi: {
    issueEmbedToken: vi.fn()
  }
}))

import { filesApi } from '@/api/files'
import { resolveEmbedUrls, stripEmbedTokens } from '@/utils/embedFiles'

const mockedIssueEmbedToken = vi.mocked(filesApi.issueEmbedToken)

beforeEach(() => {
  mockedIssueEmbedToken.mockReset()
  mockedIssueEmbedToken.mockImplementation(async (fileId: string) => ({
    file_id: fileId,
    url: `/api/files/${fileId}/stream?token=tok-${fileId}`,
    expires_at: new Date(Date.now() + 60_000).toISOString()
  }))
})

describe('embed files utils', () => {
  it('replaces stable stream references with tokenized urls', async () => {
    const html = '<img src="/api/files/file_a/stream" alt="x">'
    expect(await resolveEmbedUrls(html)).toBe('<img src="/api/files/file_a/stream?token=tok-file_a" alt="x">')
  })

  it('deduplicates token requests for repeated file ids', async () => {
    const html = '<img src="/api/files/file_a/stream"><a href="/api/files/file_a/stream">x</a>'
    const resolved = await resolveEmbedUrls(html)
    expect(resolved).toContain('token=tok-file_a')
    expect(mockedIssueEmbedToken).toHaveBeenCalledTimes(1)
  })

  it('normalizes already tokenized references before resolving', async () => {
    const html = '<img src="/api/files/file_b/stream?token=stale-token">'
    const resolved = await resolveEmbedUrls(html)
    expect(resolved).toBe('<img src="/api/files/file_b/stream?token=tok-file_b">')
  })

  it('leaves html without stream references untouched', async () => {
    const html = '<p>plain text</p>'
    expect(await resolveEmbedUrls(html)).toBe('<p>plain text</p>')
    expect(mockedIssueEmbedToken).not.toHaveBeenCalled()
  })

  it('strips embed tokens back to stable references on save', () => {
    expect(stripEmbedTokens('/api/files/file_a/stream?token=abc.def==')).toBe('/api/files/file_a/stream')
    expect(stripEmbedTokens('![x](/api/files/file_a/stream?token=a.b) ok')).toBe('![x](/api/files/file_a/stream) ok')
  })
})
