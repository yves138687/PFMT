export interface DocumentOutlineItem {
  id: string
  title: string
  level: 1 | 2 | 3 | 4 | 5 | 6
  sourceLine?: number
}

interface HeadingSeed {
  title: string
  level: 1 | 2 | 3 | 4 | 5 | 6
  sourceLine?: number
}

const headingSelector = 'h1, h2, h3, h4, h5, h6'

export function buildMarkdownOutline(source: string): DocumentOutlineItem[] {
  const headings: HeadingSeed[] = []
  let inFence = false

  const lines = source.split(/\r?\n/)
  for (const [index, line] of lines.entries()) {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence
      continue
    }
    if (inFence) {
      continue
    }

    const match = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line)
    if (!match) {
      continue
    }

    headings.push({
      level: match[1].length as DocumentOutlineItem['level'],
      sourceLine: index,
      title: stripMarkdownInline(match[2])
    })
  }

  return assignHeadingIds(headings)
}

export function buildHtmlOutline(source: string): DocumentOutlineItem[] {
  return assignHeadingIds(extractHtmlHeadings(source))
}

export function buildHtmlSourceOutline(source: string): DocumentOutlineItem[] {
  const headings: HeadingSeed[] = []
  const headingPattern = /<h([1-6])(?:\s[^>]*)?>(.*?)<\/h\1>/gi

  for (const [index, line] of source.split(/\r?\n/).entries()) {
    headingPattern.lastIndex = 0
    let match = headingPattern.exec(line)
    while (match) {
      headings.push({
        level: Number(match[1]) as DocumentOutlineItem['level'],
        sourceLine: index,
        title: stripHtml(match[2])
      })
      match = headingPattern.exec(line)
    }
  }

  return assignHeadingIds(headings)
}

export function addOutlineIdsToHtml(source: string) {
  if (!source.trim() || typeof document === 'undefined') {
    return source
  }

  const template = document.createElement('template')
  template.innerHTML = source
  const headings = Array.from(template.content.querySelectorAll<HTMLHeadingElement>(headingSelector))
  const ids = assignHeadingIds(headings.map((heading) => ({
    level: Number(heading.tagName.slice(1)) as DocumentOutlineItem['level'],
    title: normalizeTitle(heading.textContent ?? '')
  })))

  headings.forEach((heading, index) => {
    const item = ids[index]
    if (item) {
      heading.id = item.id
      heading.dataset.outlineId = item.id
    }
  })

  return template.innerHTML
}

export function applyOutlineIdsToContainer(container: HTMLElement | null) {
  if (!container) {
    return
  }

  const headings = Array.from(container.querySelectorAll<HTMLHeadingElement>(headingSelector))
  const ids = assignHeadingIds(headings.map((heading) => ({
    level: Number(heading.tagName.slice(1)) as DocumentOutlineItem['level'],
    title: normalizeTitle(heading.textContent ?? '')
  })))

  headings.forEach((heading, index) => {
    const item = ids[index]
    if (item) {
      heading.id = item.id
      heading.dataset.outlineId = item.id
    }
  })
}

function extractHtmlHeadings(source: string): HeadingSeed[] {
  if (!source.trim() || typeof document === 'undefined') {
    return []
  }

  const template = document.createElement('template')
  template.innerHTML = source
  return Array.from(template.content.querySelectorAll<HTMLHeadingElement>(headingSelector)).map((heading) => ({
    level: Number(heading.tagName.slice(1)) as DocumentOutlineItem['level'],
    title: normalizeTitle(heading.textContent ?? '')
  }))
}

function assignHeadingIds(headings: HeadingSeed[]): DocumentOutlineItem[] {
  const used = new Map<string, number>()

  return headings
    .map((heading) => ({
      ...heading,
      title: normalizeTitle(heading.title)
    }))
    .filter((heading) => heading.title)
    .map((heading) => {
      const base = slugify(heading.title)
      const count = used.get(base) ?? 0
      used.set(base, count + 1)
      return {
        ...heading,
        id: count === 0 ? base : `${base}-${count + 1}`
      }
    })
}

function slugify(value: string) {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/<[^>]+>/g, '')
    .replace(/&[a-z0-9#]+;/gi, '')
    .replace(/[^\p{L}\p{N}\s_-]/gu, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')

  return normalized || 'section'
}

function stripMarkdownInline(value: string) {
  return normalizeTitle(
    value
      .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/[`*_~]/g, '')
  )
}

function stripHtml(value: string) {
  return normalizeTitle(value.replace(/<[^>]+>/g, ''))
}

function normalizeTitle(value: string) {
  return value.replace(/\s+/g, ' ').trim()
}
