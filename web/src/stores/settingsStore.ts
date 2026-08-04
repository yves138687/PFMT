import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'

import { authApi } from '@/api/auth'
import { settingsApi } from '@/api/settings'
import type { SystemSettings } from '@/types/settings'
import { DEFAULT_SYSTEM_SETTINGS } from '@/types/settings'

function cloneSettings(settings: SystemSettings): SystemSettings {
  return {
    ...settings,
    aiProviders: settings.aiProviders.map((provider) => ({ ...provider }))
  }
}

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    settings: cloneSettings(DEFAULT_SYSTEM_SETTINGS),
    showHiddenContent: false,
    initialized: false,
    loading: false,
    saving: false
  }),
  getters: {
    hiddenFeatureEnabled: (state) => state.settings.hiddenFeatureEnabled,
    encryptionEnabled: (state) => state.settings.encryptionEnabled,
    activeAiProvider: (state) =>
      state.settings.aiProviders.find((provider) => provider.id === state.settings.activeAiProviderId) ?? null
  },
  actions: {
    async loadSettings() {
      this.loading = true
      try {
        const [settings, hiddenSession] = await Promise.all([
          settingsApi.getSettings(),
          authApi.getHiddenContentSession()
        ])
        this.settings = cloneSettings({ ...settings, showHiddenDefault: false })
        this.initialized = true
        this.showHiddenContent = this.settings.hiddenFeatureEnabled && hiddenSession.show_hidden_enabled
      } finally {
        this.loading = false
      }
    },
    async saveSettings(settings: SystemSettings) {
      this.saving = true
      try {
        const normalizedSettings = cloneSettings({ ...settings, showHiddenDefault: false })
        const savedSettings = await settingsApi.updateSettings(normalizedSettings)
        this.settings = cloneSettings({ ...savedSettings, showHiddenDefault: false })
        if (!settings.hiddenFeatureEnabled) {
          await authApi.setHiddenContentSession(false)
          this.showHiddenContent = false
        }
        ElMessage.success('系统配置已保存')
      } finally {
        this.saving = false
      }
    },
    async setShowHiddenContent(value: boolean) {
      const enabled = this.settings.hiddenFeatureEnabled && value
      const previous = this.showHiddenContent
      this.showHiddenContent = enabled
      try {
        const response = await authApi.setHiddenContentSession(enabled)
        this.showHiddenContent = this.settings.hiddenFeatureEnabled && response.show_hidden_enabled
      } catch (error) {
        this.showHiddenContent = previous
        throw error
      }
    }
  }
})
