import { describe, expect, it } from 'vitest'
import { extractDocumentImageFileId } from '@/utils/documentMedia'

describe('document media helpers', () => {
  it('extracts file id from stable stream image urls', () => {
    expect(extractDocumentImageFileId('/api/files/file_abc/stream')).toBe('file_abc')
  })

  it('extracts file id from tokenized stream image urls', () => {
    expect(extractDocumentImageFileId('/api/files/file_abc/stream?token=temporary-token')).toBe('file_abc')
  })

  it('extracts encoded file id from absolute stream urls', () => {
    expect(extractDocumentImageFileId('http://localhost/api/files/file%201/stream?token=x')).toBe('file 1')
  })

  it('ignores non-document stream urls', () => {
    expect(extractDocumentImageFileId('https://example.com/picture.png')).toBeNull()
  })
})
