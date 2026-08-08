import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'

import { authApi } from '@/api/auth'
import { settingsApi } from '@/api/settings'
import type { SystemSettings } from '@/types/settings'
import { DEFAULT_SYSTEM_SETTINGS } from '@/types/settings'

function cloneSettings(settings: SystemSettings): SystemSettings {
  return {
    ...settings,
    fileEncryption: { ...settings.fileEncryption },
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
    autoConvertTxtToMd: (state) => state.settings.autoConvertTxtToMd,
    activeAiProvider: (state) =>
      state.settings.aiProviders.find((provider) => provider.id === state.settings.activeAiProviderId) ?? null
  },
  actions: {
    async loadSettings() {
      this.loading = true
      try {
        const [settings, fileEncryption, hiddenSession] = await Promise.all([
          settingsApi.getSettings(),
          settingsApi.getFileEncryptionStatus(),
          authApi.getHiddenContentSession()
        ])
        this.settings = cloneSettings({
          ...DEFAULT_SYSTEM_SETTINGS,
          ...settings,
          encryptionEnabled: fileEncryption.encryption_enabled,
          fileEncryption,
          showHiddenDefault: false
        })
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
        this.settings = cloneSettings({
          ...savedSettings,
          showHiddenDefault: false,
          hiddenVerifyPasswordConfigured: this.settings.hiddenVerifyPasswordConfigured
        })
        if (!settings.hiddenFeatureEnabled) {
          await authApi.setHiddenContentSession(false)
          this.showHiddenContent = false
        }
        ElMessage.success('系统配置已保存')
      } finally {
        this.saving = false
      }
    },
    async enableFileEncryption(key: string) {
      const fileEncryption = await settingsApi.enableFileEncryption(key)
      this.settings.fileEncryption = fileEncryption
      this.settings.encryptionEnabled = fileEncryption.encryption_enabled
      return fileEncryption
    },
    async rotateFileEncryptionKey(key: string) {
      const fileEncryption = await settingsApi.rotateFileEncryptionKey(key)
      this.settings.fileEncryption = fileEncryption
      this.settings.encryptionEnabled = fileEncryption.encryption_enabled
      return fileEncryption
    },
    async disableFileEncryption() {
      const fileEncryption = await settingsApi.disableFileEncryption()
      this.settings.fileEncryption = fileEncryption
      this.settings.encryptionEnabled = fileEncryption.encryption_enabled
      return fileEncryption
    },
    async setShowHiddenContent(value: boolean, password?: string) {
      // 非乐观置位：等后端确认成功后再更新界面，确保目录树/文件列表在会话授权生效后才刷新。
      const enabled = this.settings.hiddenFeatureEnabled && value
      const response = await authApi.setHiddenContentSession(enabled, password)
      this.showHiddenContent = this.settings.hiddenFeatureEnabled && response.show_hidden_enabled
    },
    async saveHiddenContentPassword(currentPassword: string, newPassword: string) {
      const response = await authApi.changeHiddenContentPassword(currentPassword, newPassword)
      this.settings.hiddenVerifyPasswordConfigured = response.configured
      return response.configured
    }
  }
})
