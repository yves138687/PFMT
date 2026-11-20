/** Parse compatible headings without changing source lines or persisted content. */
export function parseMarkdownHeadings(source: string) {
  const headings: Array<{ line: number; level: number; title: string }> = []
  let fence: { marker: string; length: number } | undefined
  const content = source.split(/\r?\n/).map((line, index) => {
    const marker = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line)
    if (fence) {
      if (marker && marker[1][0] === fence.marker && marker[1].length >= fence.length && !marker[2].trim()) {
        fence = undefined
      }
      return line
    }
    if (marker && (marker[1][0] !== '`' || !marker[2].includes('`'))) {
      fence = { marker: marker[1][0], length: marker[1].length }
      return line
    }
    // Only numbered titles get the missing-space compatibility treatment.
    const normalized = line.replace(/^( {0,3}#{1,6})(?=[0-9]+(?:\.[0-9]+)*[ \t]+\S)/, '$1 ')
    const match = /^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$/.exec(normalized)
    if (match) headings.push({ line: index, level: match[1].length, title: match[2] })
    return normalized
  }).join('\n')
  return { content, headings }
}
