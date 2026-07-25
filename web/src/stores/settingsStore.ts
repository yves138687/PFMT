import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'

import { authApi } from '@/api/auth'
import { settingsApi } from '@/api/settings'
import type { SystemSettings } from '@/types/settings'
import { DEFAULT_SYSTEM_SETTINGS } from '@/types/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    settings: { ...DEFAULT_SYSTEM_SETTINGS } as SystemSettings,
    showHiddenContent: false,
    initialized: false,
    loading: false,
    saving: false
  }),
  getters: {
    hiddenFeatureEnabled: (state) => state.settings.hiddenFeatureEnabled,
    encryptionEnabled: (state) => state.settings.encryptionEnabled
  },
  actions: {
    async loadSettings() {
      this.loading = true
      try {
        const settings = await settingsApi.getSettings()
        this.settings = { ...settings, showHiddenDefault: false }
        this.initialized = true
        if (!this.settings.hiddenFeatureEnabled) {
          this.showHiddenContent = false
        }
      } finally {
        this.loading = false
      }
    },
    async saveSettings(settings: SystemSettings) {
      this.saving = true
      try {
        const normalizedSettings = { ...settings, showHiddenDefault: false }
        await settingsApi.updateSettings(normalizedSettings)
        this.settings = normalizedSettings
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
