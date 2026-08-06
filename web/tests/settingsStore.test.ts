import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi } from '@/api/auth'
import { settingsApi } from '@/api/settings'
import { useSettingsStore } from '@/stores/settingsStore'

vi.mock('@/api/auth', () => ({
  authApi: {
    getHiddenContentSession: vi.fn(),
    setHiddenContentSession: vi.fn(),
    changeHiddenContentPassword: vi.fn()
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
    vi.mocked(authApi.getHiddenContentSession).mockResolvedValue({
      show_hidden_enabled: false
    })
    vi.mocked(authApi.setHiddenContentSession).mockResolvedValue({
      show_hidden_enabled: true
    })
    vi.mocked(authApi.changeHiddenContentPassword).mockResolvedValue({
      configured: true
    })
  })

  it('loads backend setting keys into view model fields', async () => {
    vi.mocked(settingsApi.getSettings).mockResolvedValue({
      hiddenFeatureEnabled: true,
      encryptionEnabled: false,
      autoConvertTxtToMd: true,
      showHiddenDefault: true,
      hiddenVerifyPasswordConfigured: false,
      hiddenVerifyPasswordRequired: false,
      storageRootPath: 'D:/pfmt/storage',
      aiFeatureEnabled: false,
      aiProviders: [],
      activeAiProviderId: null,
      backupGitEnabled: true
    })

    const store = useSettingsStore()
    await store.loadSettings()

    expect(store.encryptionEnabled).toBe(false)
    expect(store.autoConvertTxtToMd).toBe(true)
    expect(store.showHiddenContent).toBe(false)
    expect(store.settings.showHiddenDefault).toBe(false)
    expect(store.settings.storageRootPath).toBe('D:/pfmt/storage')
    expect(authApi.getHiddenContentSession).toHaveBeenCalledTimes(1)
  })

  it('restores manually enabled hidden content from the current session after reload', async () => {
    vi.mocked(settingsApi.getSettings).mockResolvedValue({
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      autoConvertTxtToMd: false,
      showHiddenDefault: false,
      hiddenVerifyPasswordConfigured: false,
      hiddenVerifyPasswordRequired: false,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      aiProviders: [],
      activeAiProviderId: null,
      backupGitEnabled: false
    })

    const store = useSettingsStore()
    await store.setShowHiddenContent(true, 'secret-6')
    vi.mocked(authApi.getHiddenContentSession).mockResolvedValue({
      show_hidden_enabled: true
    })
    await store.loadSettings()

    expect(store.showHiddenContent).toBe(true)
  })

  it('turns off visible hidden content when hidden feature is disabled', async () => {
    vi.mocked(settingsApi.updateSettings).mockResolvedValue({
      hiddenFeatureEnabled: false,
      encryptionEnabled: true,
      autoConvertTxtToMd: false,
      showHiddenDefault: false,
      hiddenVerifyPasswordConfigured: false,
      hiddenVerifyPasswordRequired: false,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      aiProviders: [],
      activeAiProviderId: null,
      backupGitEnabled: false
    })

    const store = useSettingsStore()
    await store.setShowHiddenContent(true, 'secret-6')

    await store.saveSettings({
      hiddenFeatureEnabled: false,
      encryptionEnabled: true,
      autoConvertTxtToMd: false,
      showHiddenDefault: true,
      hiddenVerifyPasswordConfigured: false,
      hiddenVerifyPasswordRequired: false,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      aiProviders: [],
      activeAiProviderId: null,
      backupGitEnabled: false
    })

    expect(store.showHiddenContent).toBe(false)
    expect(settingsApi.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ showHiddenDefault: false })
    )
  })

  it('keeps AI provider API keys masked after saving settings', async () => {
    vi.mocked(settingsApi.updateSettings).mockResolvedValue({
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      autoConvertTxtToMd: false,
      showHiddenDefault: false,
      hiddenVerifyPasswordConfigured: false,
      hiddenVerifyPasswordRequired: false,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: true,
      aiProviders: [
        {
          id: 'openai-main',
          name: 'OpenAI 主模型',
          provider_type: 'openai_compatible',
          base_url: 'https://api.openai.com/v1',
          api_key: null,
          api_key_configured: true,
          model_name: 'gpt-4.1',
          enabled: true
        }
      ],
      activeAiProviderId: 'openai-main',
      backupGitEnabled: false
    })

    const store = useSettingsStore()
    await store.saveSettings({
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      autoConvertTxtToMd: false,
      showHiddenDefault: false,
      hiddenVerifyPasswordConfigured: false,
      hiddenVerifyPasswordRequired: false,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: true,
      aiProviders: [
        {
          id: 'openai-main',
          name: 'OpenAI 主模型',
          provider_type: 'openai_compatible',
          base_url: 'https://api.openai.com/v1',
          api_key: 'sk-secret',
          model_name: 'gpt-4.1',
          enabled: true
        }
      ],
      activeAiProviderId: 'openai-main',
      backupGitEnabled: false
    })

    expect(store.settings.aiProviders[0].api_key).toBeNull()
    expect(store.settings.aiProviders[0].api_key_configured).toBe(true)
  })

  it('forwards the second password when enabling hidden content', async () => {
    vi.mocked(settingsApi.getSettings).mockResolvedValue({
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      autoConvertTxtToMd: false,
      showHiddenDefault: false,
      hiddenVerifyPasswordConfigured: true,
      hiddenVerifyPasswordRequired: false,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      aiProviders: [],
      activeAiProviderId: null,
      backupGitEnabled: false
    })

    const store = useSettingsStore()
    await store.loadSettings()
    await store.setShowHiddenContent(true, 'secret-6')

    expect(authApi.setHiddenContentSession).toHaveBeenCalledWith(true, 'secret-6')
    expect(store.showHiddenContent).toBe(true)
  })

  it('keeps hidden content off when the backend rejects the password', async () => {
    vi.mocked(authApi.setHiddenContentSession).mockRejectedValue(new Error('二次验证码错误'))

    const store = useSettingsStore()
    await expect(store.setShowHiddenContent(true, 'wrong-xx')).rejects.toThrow('二次验证码错误')

    expect(store.showHiddenContent).toBe(false)
  })

  it('saves the hidden content password and updates the configured status', async () => {
    vi.mocked(authApi.changeHiddenContentPassword).mockResolvedValue({
      configured: true
    })

    const store = useSettingsStore()
    const configured = await store.saveHiddenContentPassword('secret-6', 'next-66')

    expect(authApi.changeHiddenContentPassword).toHaveBeenCalledWith('secret-6', 'next-66')
    expect(configured).toBe(true)
    expect(store.settings.hiddenVerifyPasswordConfigured).toBe(true)
  })
})
