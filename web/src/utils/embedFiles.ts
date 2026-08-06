/**
 * 文档内嵌文件引用工具。
 *
 * 文档内容只保存稳定引用 `/api/files/{file_id}/stream`；
 * 阅读/编辑渲染时临时换发短时效嵌入令牌（token）用于浏览器显示，
 * 保存时统一剥掉 token，保证文档内容不因令牌过期而失效。
 */

import { filesApi } from '@/api/files'

const STREAM_URL_PATTERN = /\/api\/files\/([^/"'?\s]+)\/stream/g

interface CachedToken {
  url: string
  expiresAt: number
}

const tokenCache = new Map<string, CachedToken>()

/** 获取单个文件的短时效嵌入访问链接（会话内缓存至临近过期）。 */
export async function getEmbedToken(fileId: string): Promise<string | null> {
  const cached = tokenCache.get(fileId)
  if (cached && cached.expiresAt > Date.now() + 60_000) {
    return cached.url
  }
  try {
    const response = await filesApi.issueEmbedToken(fileId)
    const expiresAt = new Date(response.expires_at).getTime()
    const url = response.url
    if (Number.isFinite(expiresAt)) {
      tokenCache.set(fileId, { url, expiresAt })
    }
    return url
  } catch {
    return null
  }
}

/** 把 HTML 字符串中的稳定文件引用批量替换为带令牌的访问链接。 */
export async function resolveEmbedUrls(html: string): Promise<string> {
  const cleanHtml = stripEmbedTokens(html)
  const fileIds = new Set<string>()
  let match: RegExpExecArray | null
  const pattern = new RegExp(STREAM_URL_PATTERN.source, 'g')
  while ((match = pattern.exec(cleanHtml)) !== null) {
    fileIds.add(match[1])
  }
  if (fileIds.size === 0) {
    return cleanHtml
  }
  const tokenByFile = new Map<string, string | null>()
  await Promise.all(
    [...fileIds].map(async (fileId) => {
      tokenByFile.set(fileId, await getEmbedToken(fileId))
    })
  )
  return cleanHtml.replace(new RegExp(STREAM_URL_PATTERN.source, 'g'), (full, fileId: string) => {
    const url = tokenByFile.get(fileId)
    return url ?? full
  })
}

/** 保存前把带令牌的引用归一为稳定引用。 */
export function stripEmbedTokens(text: string): string {
  return text.replace(/\/api\/files\/([^/"'?\s]+)\/stream\?token=[^"')\s]*/g, '/api/files/$1/stream')
}
