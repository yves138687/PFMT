import { http } from './http'
import type { SystemSettingDto, SystemSettings } from '@/types/settings'
import { DEFAULT_SYSTEM_SETTINGS, type SettingItem } from '@/types/settings'
import { boolSetting } from '@/utils/format'

type SettingsResponse = SystemSettingDto[] | { settings: SystemSettingDto[] } | Record<string, unknown>

function toBoolean(value: unknown, fallback: boolean) {
  if (value === undefined || value === null || value === '') {
    return fallback
  }

  return boolSetting(value)
}

function extractItems(response: SettingsResponse): SettingItem[] {
  if (Array.isArray(response)) {
    return response.map(toSettingItem)
  }

  if ('settings' in response && Array.isArray(response.settings)) {
    return response.settings.map(toSettingItem)
  }

  return Object.entries(response).map(([setting_key, setting_value]) => ({
    setting_key,
    setting_value: stringifySettingValue(setting_value),
    value_type: typeof setting_value === 'boolean' ? 'boolean' : 'string',
    group_name: setting_key.split('.')[0] ?? 'system',
    is_public: true
  })) satisfies SystemSettingDto[]
}

function stringifySettingValue(value: unknown) {
  if (value === undefined || value === null) {
    return null
  }

  return String(value)
}

function toSettingItem(item: SystemSettingDto): SettingItem {
  return {
    ...item,
    setting_value: stringifySettingValue(item.setting_value),
    is_public: item.is_public === true || item.is_public === 1
  }
}

export function normalizeSystemSettings(response: SettingsResponse): SystemSettings {
  const settings = { ...DEFAULT_SYSTEM_SETTINGS }
  const items = extractItems(response)

  items.forEach((item) => {
    // 这些 key 与 system_setting.setting_key 保持一致，避免页面字段和数据库字段脱节。
    switch (item.setting_key) {
      case 'hidden.feature_enabled':
        settings.hiddenFeatureEnabled = toBoolean(item.setting_value, settings.hiddenFeatureEnabled)
        break
      case 'storage.encryption_enabled':
        settings.encryptionEnabled = toBoolean(item.setting_value, settings.encryptionEnabled)
        break
      case 'hidden.show_hidden_default':
        settings.showHiddenDefault = toBoolean(item.setting_value, settings.showHiddenDefault)
        break
      case 'storage.local_root_path':
      case 'storage.local_root':
        settings.storageRootPath = String(item.setting_value ?? settings.storageRootPath)
        break
      case 'ai.feature_enabled':
        settings.aiFeatureEnabled = toBoolean(item.setting_value, settings.aiFeatureEnabled)
        break
      case 'backup.git_enabled':
        settings.backupGitEnabled = toBoolean(item.setting_value, settings.backupGitEnabled)
        break
    }
  })

  return settings
}

export function systemSettingsToDto(settings: SystemSettings): SystemSettingDto[] {
  return [
    {
      setting_key: 'hidden.feature_enabled',
      setting_value: String(settings.hiddenFeatureEnabled),
      value_type: 'boolean',
      group_name: 'hidden',
      description: '是否启用文件隐藏功能',
      is_public: 1
    },
    {
      setting_key: 'storage.encryption_enabled',
      setting_value: String(settings.encryptionEnabled),
      value_type: 'boolean',
      group_name: 'storage',
      description: '是否默认启用文件本体加密',
      is_public: 1
    },
    {
      setting_key: 'hidden.show_hidden_default',
      setting_value: String(settings.showHiddenDefault),
      value_type: 'boolean',
      group_name: 'hidden',
      description: '默认是否展示隐藏内容',
      is_public: 0
    },
    {
      setting_key: 'storage.local_root',
      setting_value: settings.storageRootPath,
      value_type: 'string',
      group_name: 'storage',
      description: '本地文件存储根路径',
      is_public: 0
    },
    {
      setting_key: 'ai.feature_enabled',
      setting_value: String(settings.aiFeatureEnabled),
      value_type: 'boolean',
      group_name: 'ai',
      description: '是否启用文件内 AI 能力',
      is_public: 1
    },
    {
      setting_key: 'backup.git_enabled',
      setting_value: String(settings.backupGitEnabled),
      value_type: 'boolean',
      group_name: 'backup',
      description: '是否启用 Git 备份能力',
      is_public: 1
    }
  ]
}

export const settingsApi = {
  async getSettings() {
    const response = await http.get<SettingsResponse>('/settings')
    return normalizeSystemSettings(response)
  },
  async updateSettings(settings: SystemSettings) {
    const responses: SystemSettingDto[] = []
    for (const item of systemSettingsToDto(settings)) {
      responses.push(
        await http.put<SystemSettingDto>(`/settings/${encodeURIComponent(item.setting_key)}`, {
          setting_value: item.setting_value,
          value_type: item.value_type,
          group_name: item.group_name,
          description: item.description,
          is_public: Boolean(item.is_public)
        })
      )
    }
    return responses
  }
}

export async function listSettingsApi() {
  const response = await http.get<SettingsResponse>('/settings')
  return extractItems(response)
}

export async function updateSettingsApi(payload: Array<Pick<SettingItem, 'setting_key' | 'setting_value'>>) {
  for (const item of payload) {
    await http.put<SystemSettingDto>(`/settings/${encodeURIComponent(item.setting_key)}`, {
      setting_value: item.setting_value
    })
  }
  return listSettingsApi()
}
