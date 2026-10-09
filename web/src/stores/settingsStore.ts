import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'

import { authApi } from '@/api/auth'
import { settingsApi } from '@/api/settings'
import type { SystemSettings } from '@/types/settings'
import { DEFAULT_SYSTEM_SETTINGS } from '@/types/settings'
import { clientLogger } from '@/utils/clientLogger'

function cloneSettings(settings: SystemSettings): SystemSettings {
  // 深拷贝可变嵌套配置，避免表单编辑直接污染 store 当前状态。
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
        clientLogger.debug('settings_load_started')
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
        clientLogger.info('settings_load_succeeded', {
          hiddenFeatureEnabled: this.settings.hiddenFeatureEnabled,
          encryptionEnabled: this.settings.encryptionEnabled,
          aiProviderCount: this.settings.aiProviders.length,
          showHiddenContent: this.showHiddenContent
        })
      } catch (error) {
        clientLogger.warn('settings_load_failed', { message: error instanceof Error ? error.message : 'unknown_error' })
        throw error
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
          // 关闭隐藏内容功能时同步关闭当前会话授权，避免界面保留已失效的显示状态。
          await authApi.setHiddenContentSession(false)
          this.showHiddenContent = false
        }
        ElMessage.success('系统配置已保存')
        clientLogger.info('settings_save_succeeded', {
          hiddenFeatureEnabled: this.settings.hiddenFeatureEnabled,
          encryptionEnabled: this.settings.encryptionEnabled,
          aiProviderCount: this.settings.aiProviders.length
        })
      } catch (error) {
        clientLogger.warn('settings_save_failed', { message: error instanceof Error ? error.message : 'unknown_error' })
        throw error
      } finally {
        this.saving = false
      }
    },
    async enableFileEncryption(key: string) {
      const fileEncryption = await settingsApi.enableFileEncryption(key)
      this.settings.fileEncryption = fileEncryption
      this.settings.encryptionEnabled = fileEncryption.encryption_enabled
      clientLogger.info('settings_file_encryption_enabled', { enabled: fileEncryption.encryption_enabled })
      return fileEncryption
    },
    async rotateFileEncryptionKey(key: string) {
      const fileEncryption = await settingsApi.rotateFileEncryptionKey(key)
      this.settings.fileEncryption = fileEncryption
      this.settings.encryptionEnabled = fileEncryption.encryption_enabled
      clientLogger.info('settings_file_encryption_rotated', { enabled: fileEncryption.encryption_enabled })
      return fileEncryption
    },
    async disableFileEncryption() {
      const fileEncryption = await settingsApi.disableFileEncryption()
      this.settings.fileEncryption = fileEncryption
      this.settings.encryptionEnabled = fileEncryption.encryption_enabled
      clientLogger.info('settings_file_encryption_disabled', { enabled: fileEncryption.encryption_enabled })
      return fileEncryption
    },
    async setShowHiddenContent(value: boolean, password?: string) {
      // 非乐观置位：等后端确认成功后再更新界面，确保目录树/文件列表在会话授权生效后才刷新。
      const enabled = this.settings.hiddenFeatureEnabled && value
      const response = await authApi.setHiddenContentSession(enabled, password)
      this.showHiddenContent = this.settings.hiddenFeatureEnabled && response.show_hidden_enabled
      clientLogger.info('settings_show_hidden_content_updated', { enabled: this.showHiddenContent })
    },
    async saveHiddenContentPassword(currentPassword: string, newPassword: string) {
      const response = await authApi.changeHiddenContentPassword(currentPassword, newPassword)
      this.settings.hiddenVerifyPasswordConfigured = response.configured
      clientLogger.info('settings_hidden_password_updated', { configured: response.configured })
      return response.configured
    }
  }
})
