import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/components/FilePropertiesDialog.vue'), 'utf-8')

describe('FilePropertiesDialog source contract', () => {
  it('wires tag suggestion generation into the existing tag editor', () => {
    expect(source).toContain('generateTagSuggestions')
    expect(source).toContain('filesApi.suggestFileTags')
    expect(source).toContain('TAG_SUGGESTION_LIMIT = 80')
    expect(source).toContain('TAG_SUGGESTION_PAGE_SIZE = 10')
    expect(source).toContain('生成建议')
    expect(source).toContain('重新生成')
    expect(source).toContain('换一批')
    expect(source).toContain('visibleTagSuggestions')
    expect(source).toContain('pagedTagSuggestions')
    expect(source).toContain('switchTagSuggestionBatch')
    expect(source).toContain('addSuggestedTag')
    expect(source).toContain('暂无可添加建议')
    expect(source).toContain('filesApi.updateFileTags')
  })
})
