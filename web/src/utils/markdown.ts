import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { parseMarkdownHeadings } from './markdownHeadings'

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

export function renderMarkdown(source: string) {
  // Markdown 文件只做查看：先禁用原始 HTML，再用 DOMPurify 做二次净化，避免预览页执行脚本。
  return DOMPurify.sanitize(markdown.render(parseMarkdownHeadings(source).content), {
    USE_PROFILES: { html: true }
  })
}
