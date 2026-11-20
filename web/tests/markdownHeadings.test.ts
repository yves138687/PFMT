import { describe, expect, it } from 'vitest'
import { parseMarkdownHeadings } from '@/utils/markdownHeadings'
import { buildMarkdownOutline } from '@/utils/documentOutline'
import { buildReadSections } from '@/utils/documentReading'
import { renderMarkdown } from '@/utils/markdown'

describe('numbered Markdown heading compatibility', () => {
  it('keeps outline, chapter splitting and rendered heading levels consistent', () => {
    const source = '#1 开始\n\n正文\n\n##2 小节\n\n###1.1 背景\n\n# 标准标题\n\n结尾'
    expect(buildMarkdownOutline(source).map(({ title, level, sourceLine }) => ({ title, level, sourceLine }))).toEqual([
      { title: '1 开始', level: 1, sourceLine: 0 },
      { title: '2 小节', level: 2, sourceLine: 4 },
      { title: '1.1 背景', level: 3, sourceLine: 6 },
      { title: '标准标题', level: 1, sourceLine: 8 }
    ])
    const sections = buildReadSections(source, 'markdown')
    expect(sections.map(({ title }) => title)).toEqual(['1 开始', '标准标题'])
    expect(sections[0].content).toContain('#1 开始')
    const html = renderMarkdown(source)
    expect(html).toContain('<h1>1 开始</h1>')
    expect(html).toContain('<h2>2 小节</h2>')
    expect(html).toContain('<h3>1.1 背景</h3>')
    expect(html).toContain('<h1>标准标题</h1>')
  })

  it('does not promote tags, escaped hashes, code or titles without separating whitespace', () => {
    const source = ['#标签', '#FFFFFF', '#1标题', '#1', '\\#1 转义', '正文 #1 内联',
      '', '    #1 缩进代码', '\t#2 制表符代码', '', '```md', '#3 围栏代码', '```',
      '', '~~~', '#4 另一围栏', '~~~'].join('\n')
    expect(parseMarkdownHeadings(source).content).toBe(source)
    expect(buildMarkdownOutline(source)).toEqual([])
    expect(renderMarkdown(source)).not.toMatch(/<h[1-6]>/)
  })

  it('requires a matching fence marker and sufficient closing length', () => {
    const source = ['````md', '#1 代码', '~~~', '#2 仍是代码', '```', '#3 仍是代码',
      '````', '#4 真正标题', '#5 下一章'].join('\n')
    expect(buildMarkdownOutline(source).map(({ title }) => title)).toEqual(['4 真正标题', '5 下一章'])
    expect(renderMarkdown(source)).toContain('<h1>4 真正标题</h1>')
    expect(renderMarkdown(source)).not.toContain('<h1>3 仍是代码</h1>')
  })

  it('supports up to six levels, CRLF, closing hashes and up to three leading spaces', () => {
    const source = '   ######12.3 标题 ###\r\n\r\n#######7 超出层级'
    expect(buildMarkdownOutline(source)).toMatchObject([{ title: '12.3 标题', level: 6, sourceLine: 0 }])
    expect(renderMarkdown(source)).toContain('<h6>12.3 标题</h6>')
  })
})
