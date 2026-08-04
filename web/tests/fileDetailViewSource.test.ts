import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/views/files/FileDetailView.vue'), 'utf-8')

describe('FileDetailView source contract', () => {
  it('offers single file export from the detail page', () => {
    expect(source).toContain('导出')
    expect(source).toContain('exportCurrentFile')
    expect(source).toContain('filesApi.exportFile')
    expect(source).toContain('saveBlobResponse')
    expect(source).toContain(':loading="exportLoading"')
  })
})
