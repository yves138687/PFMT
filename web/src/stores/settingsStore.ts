import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'

import { settingsApi } from '@/api/settings'
import type { SystemSettings } from '@/types/settings'
import { DEFAULT_SYSTEM_SETTINGS } from '@/types/settings'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    settings: { ...DEFAULT_SYSTEM_SETTINGS } as SystemSettings,
    showHiddenContent: DEFAULT_SYSTEM_SETTINGS.showHiddenDefault,
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
        this.settings = settings
        if (!this.initialized) {
          // 首次加载时才采用系统默认值，避免覆盖用户在当前会话里手动切换的显示隐藏内容状态。
          this.showHiddenContent = settings.hiddenFeatureEnabled && settings.showHiddenDefault
        }
        this.initialized = true
      } finally {
        this.loading = false
      }
    },
    async saveSettings(settings: SystemSettings) {
      this.saving = true
      try {
        await settingsApi.updateSettings(settings)
        this.settings = { ...settings }
        if (!settings.hiddenFeatureEnabled) {
          this.showHiddenContent = false
        }
        ElMessage.success('系统配置已保存')
      } finally {
        this.saving = false
      }
    },
    setShowHiddenContent(value: boolean) {
      this.showHiddenContent = this.settings.hiddenFeatureEnabled && value
    }
  }
})
