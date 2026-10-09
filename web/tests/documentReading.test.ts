import { describe, expect, it } from 'vitest'
import { buildReadSections } from '@/utils/documentReading'

describe('buildReadSections', () => {
  it('prefers top-level Markdown chapters and keeps nested headings with their chapter', () => {
    const sections = buildReadSections('# 第一章\n\n内容\n\n## 小节\n\n更多内容\n\n# 第二章\n\n结尾', 'markdown')
    expect(sections).toHaveLength(2)
    expect(sections[0]).toMatchObject({ title: '第一章', sourceLine: 0 })
    expect(sections[0].content).toContain('## 小节')
  })

  it('uses bounded paragraph sections when no chapters exist', () => {
    const sections = buildReadSections('一\n\n二\n\n三\n\n四\n\n五', 'plain_text', 2)
    expect(sections.map((section) => section.content)).toEqual(['一\n\n二', '三\n\n四', '五'])
  })
})
