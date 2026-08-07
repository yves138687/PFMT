const DOCUMENT_STREAM_IMAGE_PATTERN = /\/api\/files\/([^/"'?\s]+)\/stream(?:\?[^"'()\s]*)?/

export function extractDocumentImageFileId(src: string | null | undefined): string | null {
  if (!src) {
    return null
  }
  try {
    const baseUrl = typeof window === 'undefined' ? 'http://localhost' : window.location.origin
    const url = new URL(src, baseUrl)
    const match = url.pathname.match(/^\/api\/files\/([^/]+)\/stream$/)
    return match ? decodeURIComponent(match[1]) : null
  } catch {
    const match = src.match(DOCUMENT_STREAM_IMAGE_PATTERN)
    return match ? decodeURIComponent(match[1]) : null
  }
}
