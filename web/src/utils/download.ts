export interface DownloadBlobResponse {
  blob: Blob
  headers: Headers
}

function decodeFilename(value: string) {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export function filenameFromDisposition(disposition: string | null, fallback: string) {
  if (!disposition) {
    return fallback
  }

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeFilename(utf8Match[1].trim().replace(/^"|"$/g, ''))
  }

  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i)
  if (filenameMatch?.[1]) {
    return filenameMatch[1].trim()
  }

  return fallback
}

export function saveBlobResponse(response: DownloadBlobResponse, fallbackName: string) {
  const filename = filenameFromDisposition(response.headers.get('content-disposition'), fallbackName)
  const url = URL.createObjectURL(response.blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
