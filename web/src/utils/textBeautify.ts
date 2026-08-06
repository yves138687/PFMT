/**
 * 文本整理工具（安全版）
 *
 * - plain_text：完整整理（统一换行符、去头尾空白、清理行尾空格、单换行加倍、折叠多余空行）。
 *   纯文本没有格式语义，单换行加倍不会破坏任何渲染结构。
 * - markdown：只做渲染安全的整理（统一换行符、去头尾空白、围栏感知地折叠多余空行）。
 *   不做单换行加倍（会毁掉表格/拆散引用块/改动代码），不做行尾空格清理（保留两空格硬换行）。
 * - html：仅统一换行符 + 去头尾空白，其余不动。
 */

export type BeautifyTarget = 'plain_text' | 'markdown' | 'html'

/** 统一换行符：CRLF / 孤立 CR 一律转为 LF。 */
export function normalizeLineEndings(text: string): string {
  return text.replace(/\r\n?/g, '\n')
}

/** 去除文本整体头尾空白（含换行、制表符等）。 */
export function trimOuterWhitespace(text: string): string {
  return text.replace(/^\s+|\s+$/g, '')
}

/** 清理每行行尾的空格/制表符。 */
export function trimLineTrailingWhitespace(text: string): string {
  return text.replace(/[ \t]+$/gm, '')
}

/** 单个换行加倍为两个换行，不影响已有空行。 */
export function doubleSingleNewlines(text: string): string {
  return text.replace(/(?<!\n)\n(?!\n)/g, '\n\n')
}

/** 连续 3 个及以上换行折叠为单个空行（两个换行）。 */
export function collapseBlankLines(text: string): string {
  return text.replace(/\n{3,}/g, '\n\n')
}

/** 围栏感知地折叠多余空行：``` / ~~~ 围栏内部完全保留，围栏外连续空行折叠为单个空行。 */
export function collapseBlankLinesOutsideFences(text: string): string {
  const lines = text.split('\n')
  const output: string[] = []
  let insideFence = false

  for (const line of lines) {
    const isFenceLine = /^ {0,3}(`{3,}|~{3,})/.test(line)
    if (isFenceLine) {
      insideFence = !insideFence
      output.push(line)
      continue
    }
    if (insideFence) {
      output.push(line)
      continue
    }
    if (line === '') {
      if (output.length > 0 && output[output.length - 1] !== '') {
        output.push('')
      }
      continue
    }
    output.push(line)
  }

  return output.join('\n')
}

/** 按文档格式整理文本。 */
export function beautifyText(text: string, format: BeautifyTarget): string {
  const normalized = normalizeLineEndings(text)
  const trimmed = trimOuterWhitespace(normalized)

  if (format === 'html') {
    return trimmed
  }
  if (format === 'markdown') {
    return collapseBlankLinesOutsideFences(trimmed)
  }

  const noTrailingWhitespace = trimLineTrailingWhitespace(trimmed)
  const doubled = doubleSingleNewlines(noTrailingWhitespace)
  return collapseBlankLines(doubled)
}
