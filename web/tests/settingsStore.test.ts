import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi } from '@/api/auth'
import { settingsApi } from '@/api/settings'
import { useSettingsStore } from '@/stores/settingsStore'

vi.mock('@/api/auth', () => ({
  authApi: {
    setHiddenContentSession: vi.fn()
  }
}))

vi.mock('@/api/settings', () => ({
  settingsApi: {
    getSettings: vi.fn(),
    updateSettings: vi.fn()
  }
}))

describe('settings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(authApi.setHiddenContentSession).mockResolvedValue({
      show_hidden_enabled: true
    })
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
    expect(store.showHiddenContent).toBe(false)
    expect(store.settings.showHiddenDefault).toBe(false)
    expect(store.settings.storageRootPath).toBe('D:/pfmt/storage')
  })

  it('keeps manually enabled hidden content only in the current session', async () => {
    vi.mocked(settingsApi.getSettings).mockResolvedValue({
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      showHiddenDefault: false,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      backupGitEnabled: false
    })

    const store = useSettingsStore()
    await store.setShowHiddenContent(true)
    await store.loadSettings()

    expect(store.showHiddenContent).toBe(true)
  })

  it('turns off visible hidden content when hidden feature is disabled', async () => {
    vi.mocked(settingsApi.updateSettings).mockResolvedValue([])

    const store = useSettingsStore()
    await store.setShowHiddenContent(true)

    await store.saveSettings({
      hiddenFeatureEnabled: false,
      encryptionEnabled: true,
      showHiddenDefault: true,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      backupGitEnabled: false
    })

    expect(store.showHiddenContent).toBe(false)
    expect(settingsApi.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ showHiddenDefault: false })
    )
  })
})
