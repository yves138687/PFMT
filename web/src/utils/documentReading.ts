import type { DocumentFormat } from '@/types/files'

export interface ReadSection {
  title: string
  content: string
  /** Source line where the section starts; used to match Markdown outline entries. */
  sourceLine: number
}

const DEFAULT_PARAGRAPHS_PER_SECTION = 60

/**
 * Splits a document into small renderable units for read mode. Documents with
 * headings are split by their top-level heading; all other documents fall back
 * to a bounded number of logical paragraphs.
 */
export function buildReadSections(
  source: string,
  format: DocumentFormat,
  paragraphsPerSection = DEFAULT_PARAGRAPHS_PER_SECTION
): ReadSection[] {
  if (!source) {
    return [{ title: '正文', content: '', sourceLine: 0 }]
  }

  const chapterSections = format === 'markdown'
    ? splitMarkdownChapters(source)
    : format === 'html'
      ? splitHtmlChapters(source)
      : []

  return chapterSections.length > 1
    ? chapterSections
    : splitParagraphs(source, Math.max(1, paragraphsPerSection))
}

function splitMarkdownChapters(source: string): ReadSection[] {
  const lines = source.split(/\r?\n/)
  let inFence = false
  const headings: Array<{ line: number; level: number; title: string }> = []

  lines.forEach((line, index) => {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence
      return
    }
    if (inFence) return
    const match = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line)
    if (match) headings.push({ line: index, level: match[1].length, title: stripMarkdown(match[2]) })
  })
  if (headings.length < 2) return []

  const chapterLevel = Math.min(...headings.map((heading) => heading.level))
  const chapters = headings.filter((heading) => heading.level === chapterLevel)
  if (chapters.length < 2) return []

  return chapters.map((chapter, index) => ({
    title: chapter.title || `第 ${index + 1} 节`,
    content: lines.slice(chapter.line, chapters[index + 1]?.line).join('\n'),
    sourceLine: chapter.line
  }))
}

function splitHtmlChapters(source: string): ReadSection[] {
  const headings = Array.from(source.matchAll(/<h([1-6])(?:\s[^>]*)?>([\s\S]*?)<\/h\1>/gi))
  if (headings.length < 2) return []
  const chapterLevel = Math.min(...headings.map((heading) => Number(heading[1])))
  const chapters = headings.filter((heading) => Number(heading[1]) === chapterLevel)
  if (chapters.length < 2) return []

  return chapters.map((chapter, index) => ({
    title: stripHtml(chapter[2]) || `第 ${index + 1} 节`,
    content: source.slice(chapter.index, chapters[index + 1]?.index),
    sourceLine: countLinesBefore(source, chapter.index ?? 0)
  }))
}

function splitParagraphs(source: string, paragraphsPerSection: number): ReadSection[] {
  const paragraphs = source.split(/(?:\r?\n){2,}/).filter((paragraph) => paragraph.trim())
  if (paragraphs.length === 0) return [{ title: '正文', content: source, sourceLine: 0 }]

  return Array.from({ length: Math.ceil(paragraphs.length / paragraphsPerSection) }, (_, index) => {
    const content = paragraphs.slice(index * paragraphsPerSection, (index + 1) * paragraphsPerSection).join('\n\n')
    const prefix = paragraphs.slice(0, index * paragraphsPerSection).join('\n\n')
    return {
      title: `第 ${index + 1} 段`,
      content,
      sourceLine: prefix ? prefix.split(/\r?\n/).length + 1 : 0
    }
  })
}

function stripMarkdown(value: string) {
  return value.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/[`*_~]/g, '').trim()
}

function stripHtml(value: string) {
  return value.replace(/<[^>]+>/g, '').replace(/&nbsp;/gi, ' ').trim()
}

function countLinesBefore(source: string, position: number) {
  return source.slice(0, position).split(/\r?\n/).length - 1
}
