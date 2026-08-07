/**
 * Tiptap 编辑器 JSON → Markdown 序列化。
 *
 * 与后端文档格式约定保持一致：图片引用保存为 `/api/files/{file_id}/stream`（不含令牌），
 * 表格保存为标准 GFM 管道表格。
 */

export type ProseMirrorNode = {
  type?: string
  text?: string
  attrs?: Record<string, unknown>
  marks?: Array<{ type?: string; attrs?: Record<string, unknown> }>
  content?: ProseMirrorNode[]
}

export function serializeMarkdownDocument(node: ProseMirrorNode | undefined): string {
  if (!node?.content) {
    return ''
  }
  return node.content.map((child) => serializeMarkdownBlock(child, 0)).join('\n\n').trimEnd()
}

function serializeMarkdownBlock(node: ProseMirrorNode, depth: number): string {
  const children = node.content ?? []
  if (node.type === 'heading') {
    const level = Number(node.attrs?.level ?? 1)
    return `${'#'.repeat(Math.min(Math.max(level, 1), 6))} ${serializeInline(children)}`
  }
  if (node.type === 'paragraph') {
    return serializeInline(children)
  }
  if (node.type === 'image') {
    return serializeImage(node)
  }
  if (node.type === 'bulletList') {
    return children.map((child) => serializeListItem(child, depth, '-')).join('\n')
  }
  if (node.type === 'orderedList') {
    return children.map((child, index) => serializeListItem(child, depth, `${index + 1}.`)).join('\n')
  }
  if (node.type === 'blockquote') {
    return children
      .map((child) => serializeMarkdownBlock(child, depth))
      .join('\n')
      .split('\n')
      .map((line) => `> ${line}`)
      .join('\n')
  }
  if (node.type === 'codeBlock') {
    return `\`\`\`\n${serializeInline(children)}\n\`\`\``
  }
  if (node.type === 'horizontalRule') {
    return '---'
  }
  if (node.type === 'table') {
    return serializeTable(node)
  }
  return serializeInline(children)
}

function serializeListItem(node: ProseMirrorNode, depth: number, marker: string): string {
  const indent = '  '.repeat(depth)
  const blocks = node.content ?? []
  const [firstBlock, ...restBlocks] = blocks
  const firstLine = firstBlock ? serializeMarkdownBlock(firstBlock, depth + 1) : ''
  const rest = restBlocks.map((child) => serializeMarkdownBlock(child, depth + 1)).filter(Boolean)
  const first = `${indent}${marker} ${firstLine}`
  return [first, ...rest.map((line) => `${indent}  ${line}`)].join('\n')
}

function serializeInline(nodes: ProseMirrorNode[]): string {
  return nodes
    .map((node) => {
      if (node.type === 'text') {
        return applyMarkdownMarks(node.text ?? '', node.marks ?? [])
      }
      if (node.type === 'hardBreak') {
        return '  \n'
      }
      if (node.type === 'image') {
        return serializeImage(node)
      }
      return serializeInline(node.content ?? [])
    })
    .join('')
}

function serializeImage(node: ProseMirrorNode): string {
  const attrs = node.attrs ?? {}
  const src = typeof attrs.src === 'string' ? attrs.src : ''
  if (!src) {
    return ''
  }
  const alt = typeof attrs.alt === 'string' ? attrs.alt : ''
  const rawTitle = typeof attrs.title === 'string' ? attrs.title : ''
  const title = rawTitle ? ` "${rawTitle.replace(/"/g, '\\"')}"` : ''
  return `![${alt}](${src}${title})`
}

function serializeTable(node: ProseMirrorNode): string {
  const rows = (node.content ?? []).map((row) => (row.content ?? []).map(serializeTableCell))
  if (rows.length === 0) {
    return ''
  }
  const columnCount = Math.max(...rows.map((row) => row.length))
  const padRow = (cells: string[]): string[] => {
    const padded = [...cells]
    while (padded.length < columnCount) {
      padded.push('')
    }
    return padded
  }
  const headerCells = padRow(rows[0])
  const lines = [
    `| ${headerCells.join(' | ')} |`,
    `| ${headerCells.map(() => '---').join(' | ')} |`
  ]
  const firstRowIsHeader = rows[0][0] !== undefined && node.content?.[0]?.content?.[0]?.type === 'tableHeader'
  const bodyStart = firstRowIsHeader ? 1 : 0
  for (let index = bodyStart; index < rows.length; index += 1) {
    lines.push(`| ${padRow(rows[index]).join(' | ')} |`)
  }
  return lines.join('\n')
}

function serializeTableCell(cell: ProseMirrorNode): string {
  const text = serializeInline(cell.content ?? [])
  return text.replace(/\|/g, '\\|').replace(/\n/g, ' ')
}

function applyMarkdownMarks(text: string, marks: NonNullable<ProseMirrorNode['marks']>): string {
  return marks.reduce((result, mark) => {
    if (mark.type === 'bold') {
      return `**${result}**`
    }
    if (mark.type === 'italic') {
      return `*${result}*`
    }
    if (mark.type === 'code') {
      return `\`${result}\``
    }
    if (mark.type === 'strike') {
      return `~~${result}~~`
    }
    if (mark.type === 'link' && typeof mark.attrs?.href === 'string') {
      return `[${result}](${mark.attrs.href})`
    }
    return result
  }, text)
}
