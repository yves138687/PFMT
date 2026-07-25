import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const source = readFileSync(
  resolve(process.cwd(), 'src/components/FileUploadDialog.vue'),
  'utf-8'
)

describe('FileUploadDialog source contract', () => {
  it('uploads directly to the provided current folder without a path selector', () => {
    expect(source).toContain('targetPathId')
    expect(source).toContain('pathId: props.targetPathId')
    expect(source).toContain('上传到：{{ targetFullPath }}')
    expect(source).not.toContain('<el-select')
  })
})
