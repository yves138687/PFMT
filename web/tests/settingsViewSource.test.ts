import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const source = readFileSync(
  resolve(process.cwd(), 'src/views/settings/SettingsView.vue'),
  'utf-8'
)

describe('SettingsView source contract', () => {
  it('offers an upload option for automatic txt to markdown conversion', () => {
    expect(source).toContain('上传设置')
    expect(source).toContain('form.autoConvertTxtToMd')
    expect(source).toContain('TXT 转 Markdown')
  })

  it('supports AI provider list management and default model selection', () => {
    expect(source).toContain('AI 设置')
    expect(source).toContain('addAiProvider')
    expect(source).toContain('removeAiProvider')
    expect(source).toContain('form.activeAiProviderId')
    expect(source).toContain('providerTypeOptions')
    expect(source).toContain('api_key_configured')
    expect(source).toContain('留空则不覆盖')
    expect(source).toContain('新增配置')
  })
})
