import { describe, expect, it } from 'vitest'
import { boolSetting, formatFileSize } from '@/utils/format'

describe('format utils', () => {
  it('formats file size for file browser display', () => {
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(2048)).toBe('2.00 KB')
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5.00 MB')
  })

  it('parses boolean system setting values', () => {
    expect(boolSetting('true')).toBe(true)
    expect(boolSetting('1')).toBe(true)
    expect(boolSetting('false')).toBe(false)
    expect(boolSetting(null)).toBe(false)
  })
})
