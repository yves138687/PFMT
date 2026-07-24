import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { settingsApi } from '@/api/settings'
import { useSettingsStore } from '@/stores/settingsStore'

vi.mock('@/api/settings', () => ({
  settingsApi: {
    getSettings: vi.fn(),
    updateSettings: vi.fn()
  }
}))

describe('settings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads backend setting keys into view model fields', async () => {
    vi.mocked(settingsApi.getSettings).mockResolvedValue({
      hiddenFeatureEnabled: true,
      encryptionEnabled: false,
      showHiddenDefault: true,
      storageRootPath: 'D:/pfmt/storage',
      aiFeatureEnabled: false,
      backupGitEnabled: true
    })

    const store = useSettingsStore()
    await store.loadSettings()

    expect(store.encryptionEnabled).toBe(false)
    expect(store.showHiddenContent).toBe(true)
    expect(store.settings.storageRootPath).toBe('D:/pfmt/storage')
  })

  it('turns off visible hidden content when hidden feature is disabled', async () => {
    vi.mocked(settingsApi.updateSettings).mockResolvedValue([])

    const store = useSettingsStore()
    store.setShowHiddenContent(true)

    await store.saveSettings({
      hiddenFeatureEnabled: false,
      encryptionEnabled: true,
      showHiddenDefault: true,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      backupGitEnabled: false
    })

    expect(store.showHiddenContent).toBe(false)
    expect(settingsApi.updateSettings).toHaveBeenCalledOnce()
  })
})
