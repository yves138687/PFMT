import { describe, expect, it } from 'vitest'
import {
  beautifyText,
  collapseBlankLines,
  doubleSingleNewlines,
  normalizeLineEndings,
  trimLineTrailingWhitespace,
  trimOuterWhitespace
} from '@/utils/textBeautify'

describe('text beautify utils', () => {
  describe('step helpers', () => {
    it('normalizes CRLF and lone CR to LF', () => {
      expect(normalizeLineEndings('a\r\nb\rc')).toBe('a\nb\nc')
    })

    it('trims outer whitespace including newlines and tabs', () => {
      expect(trimOuterWhitespace('  \n\t正文  \n')).toBe('正文')
      expect(trimOuterWhitespace(' \n ')).toBe('')
    })

    it('removes trailing spaces and tabs per line', () => {
      expect(trimLineTrailingWhitespace('a  \nb\t\nc')).toBe('a\nb\nc')
    })

    it('doubles single newlines without touching blank lines', () => {
      expect(doubleSingleNewlines('a\nb\n\nc')).toBe('a\n\nb\n\nc')
    })

    it('collapses 3+ newlines into a single blank line', () => {
      expect(collapseBlankLines('a\n\n\n\nb')).toBe('a\n\nb')
    })
  })

  describe('plain_text full rules', () => {
    it('normalizes line endings and doubles single newlines', () => {
      expect(beautifyText('第一行\r\n第二行', 'plain_text')).toBe('第一行\n\n第二行')
    })

    it('removes head and tail whitespace', () => {
      expect(beautifyText('  \n  你好  \n', 'plain_text')).toBe('你好')
    })

    it('doubles single newlines while preserving existing blank lines', () => {
      expect(beautifyText('a\nb\n\nc', 'plain_text')).toBe('a\n\nb\n\nc')
    })

    it('cleans trailing whitespace per line', () => {
      expect(beautifyText('a  \nb\t\nc', 'plain_text')).toBe('a\n\nb\n\nc')
    })

    it('collapses 3+ newlines into one blank line', () => {
      expect(beautifyText('a\n\n\n\nb', 'plain_text')).toBe('a\n\nb')
    })

    it('returns empty string for empty or whitespace-only input', () => {
      expect(beautifyText('', 'plain_text')).toBe('')
      expect(beautifyText(' \n\t ', 'plain_text')).toBe('')
    })

    it('does not leave a trailing newline', () => {
      expect(beautifyText('a\nb\n\n', 'plain_text')).toBe('a\n\nb')
    })

    it('is idempotent', () => {
      const input = '  \r\n第一行\r\n第二行\n\n\n第三行  \n'
      const once = beautifyText(input, 'plain_text')
      expect(beautifyText(once, 'plain_text')).toBe(once)
    })
  })

  describe('markdown safe cleanup only', () => {
    it('does not double single newlines (tight list stays adjacent)', () => {
      expect(beautifyText('- 苹果\n- 香蕉', 'markdown')).toBe('- 苹果\n- 香蕉')
    })

    it('keeps table rows adjacent', () => {
      const table = '| 名称 | 值 |\n| --- | --- |\n| a | 1 |'
      expect(beautifyText(table, 'markdown')).toBe(table)
    })

    it('preserves trailing two-space hard breaks', () => {
      expect(beautifyText('第一行  \n第二行', 'markdown')).toBe('第一行  \n第二行')
    })

    it('preserves fenced code block interior unchanged', () => {
      const source = '```js\nconst a = 1\n\nconst b = 2  \n```'
      expect(beautifyText(source, 'markdown')).toBe(source)
    })

    it('does not collapse blank lines inside fences', () => {
      const source = '```js\na\n\n\n\nb\n```'
      expect(beautifyText(source, 'markdown')).toBe(source)
    })

    it('collapses blank lines outside fences', () => {
      expect(beautifyText('a\n\n\n\nb', 'markdown')).toBe('a\n\nb')
    })

    it('normalizes line endings and trims outer whitespace', () => {
      expect(beautifyText('  \r\n# 标题  \n', 'markdown')).toBe('# 标题')
    })
  })

  describe('html minimal cleanup', () => {
    it('only normalizes line endings and trims outer whitespace', () => {
      expect(beautifyText('<div>\r\n  <p>a</p>\r\n</div>', 'html')).toBe('<div>\n  <p>a</p>\n</div>')
    })

    it('does not double single newlines', () => {
      expect(beautifyText('<p>a</p>\n<p>b</p>', 'html')).toBe('<p>a</p>\n<p>b</p>')
    })

    it('does not collapse blank lines', () => {
      expect(beautifyText('<p>a</p>\n\n\n<p>b</p>', 'html')).toBe('<p>a</p>\n\n\n<p>b</p>')
    })
  })

  describe('no-op for well-formed text', () => {
    it('keeps clean plain text unchanged', () => {
      const clean = '第一段\n\n第二段'
      expect(beautifyText(clean, 'plain_text')).toBe(clean)
    })

    it('keeps clean markdown unchanged', () => {
      const clean = '# 标题\n\n正文'
      expect(beautifyText(clean, 'markdown')).toBe(clean)
    })

    it('keeps clean html unchanged', () => {
      const clean = '<p>正文</p>'
      expect(beautifyText(clean, 'html')).toBe(clean)
    })
  })
})
