import { describe, expect, it } from 'vitest'
import { serializeMarkdownDocument, type ProseMirrorNode } from '@/utils/documentMarkdown'

function text(value: string, marks: Array<{ type: string; attrs?: Record<string, unknown> }> = []): ProseMirrorNode {
  return { type: 'text', text: value, marks }
}

function paragraph(...content: ProseMirrorNode[]): ProseMirrorNode {
  return { type: 'paragraph', content }
}

describe('document markdown serializer', () => {
  it('serializes headings, paragraphs and inline marks', () => {
    const doc: ProseMirrorNode = {
      content: [
        { type: 'heading', attrs: { level: 2 }, content: [text('标题')] },
        paragraph(text('加粗', [{ type: 'bold' }]), text(' 和 '), text('链接', [{ type: 'link', attrs: { href: 'https://example.com' } }]))
      ]
    }
    expect(serializeMarkdownDocument(doc)).toBe('## 标题\n\n**加粗** 和 [链接](https://example.com)')
  })

  it('serializes image nodes to markdown image syntax', () => {
    const doc: ProseMirrorNode = {
      content: [
        paragraph({ type: 'image', attrs: { src: '/api/files/file_abc/stream', alt: '示意图' } })
      ]
    }
    expect(serializeMarkdownDocument(doc)).toBe('![示意图](/api/files/file_abc/stream)')
  })

  it('serializes top-level image nodes inserted by the editor', () => {
    const doc: ProseMirrorNode = {
      content: [
        { type: 'image', attrs: { src: '/api/files/file_top/stream', alt: '截图' } },
        paragraph(text('说明'))
      ]
    }
    expect(serializeMarkdownDocument(doc)).toBe('![截图](/api/files/file_top/stream)\n\n说明')
  })

  it('serializes image title when present', () => {
    const doc: ProseMirrorNode = {
      content: [
        paragraph({ type: 'image', attrs: { src: '/api/files/file_abc/stream', alt: '图', title: '说明' } })
      ]
    }
    expect(serializeMarkdownDocument(doc)).toBe('![图](/api/files/file_abc/stream "说明")')
  })

  it('serializes tables as GFM pipe tables with header row', () => {
    const doc: ProseMirrorNode = {
      content: [
        {
          type: 'table',
          content: [
            {
              type: 'tableRow',
              content: [
                { type: 'tableHeader', content: [paragraph(text('名称'))] },
                { type: 'tableHeader', content: [paragraph(text('说明'))] }
              ]
            },
            {
              type: 'tableRow',
              content: [
                { type: 'tableCell', content: [paragraph(text('甲|乙'))] },
                { type: 'tableCell', content: [paragraph(text('一'))] }
              ]
            }
          ]
        }
      ]
    }
    expect(serializeMarkdownDocument(doc)).toBe('| 名称 | 说明 |\n| --- | --- |\n| 甲\\|乙 | 一 |')
  })

  it('keeps lists, blockquote, code block and horizontal rule', () => {
    const doc: ProseMirrorNode = {
      content: [
        { type: 'bulletList', content: [{ type: 'listItem', content: [paragraph(text('a'))] }, { type: 'listItem', content: [paragraph(text('b'))] }] },
        { type: 'blockquote', content: [paragraph(text('引文'))] },
        { type: 'codeBlock', content: [{ type: 'text', text: 'const x = 1' }] },
        { type: 'horizontalRule' }
      ]
    }
    expect(serializeMarkdownDocument(doc)).toBe('- a\n- b\n\n> 引文\n\n```\nconst x = 1\n```\n\n---')
  })
})
