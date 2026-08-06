import { http } from './http'
import type { AiProviderConfig, AiProviderType, SystemSettingDto, SystemSettings } from '@/types/settings'
import { DEFAULT_SYSTEM_SETTINGS, type SettingItem } from '@/types/settings'
import { boolSetting } from '@/utils/format'

type SettingsResponse = SystemSettingDto[] | { settings: SystemSettingDto[] } | Record<string, unknown>

function inferSettingValueType(value: unknown) {
  if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
    return 'json'
  }

  return typeof value === 'boolean' ? 'boolean' : 'string'
}

function toBoolean(value: unknown, fallback: boolean) {
  if (value === undefined || value === null || value === '') {
    return fallback
  }

  return boolSetting(value)
}

function toStringOrNull(value: unknown) {
  if (value === undefined || value === null) {
    return null
  }

  return String(value)
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
    setting_value: normalizeSettingValue(setting_value),
    value_type: inferSettingValueType(setting_value),
    group_name: setting_key.split('.')[0] ?? 'system',
    is_public: true
  })) satisfies SystemSettingDto[]
}

function normalizeSettingValue(value: unknown): SystemSettingDto['setting_value'] {
  if (value === undefined || value === null) {
    return null
  }

  if (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string') {
    return value
  }

  if (Array.isArray(value)) {
    return value as AiProviderConfig[]
  }

  return String(value)
}

function toSettingItem(item: SystemSettingDto): SettingItem {
  return {
    ...item,
    setting_value: normalizeSettingValue(item.setting_value),
    is_public: item.is_public === true || item.is_public === 1
  }
}

function normalizeAiProviderType(value: unknown): AiProviderType {
  if (value === 'ollama' || value === 'custom') {
    return value
  }

  return 'openai_compatible'
}

function normalizeAiProviders(value: unknown): AiProviderConfig[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item, index) => ({
      id: String(item.id || `ai-provider-${index + 1}`),
      name: String(item.name || 'AI 模型'),
      provider_type: normalizeAiProviderType(item.provider_type),
      base_url: String(item.base_url || ''),
      api_key: typeof item.api_key === 'string' ? item.api_key : null,
      api_key_configured: Boolean(item.api_key_configured),
      model_name: String(item.model_name || ''),
      enabled: item.enabled === undefined ? true : boolSetting(item.enabled)
    }))
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
      case 'document.auto_convert_txt_to_md':
        settings.autoConvertTxtToMd = toBoolean(item.setting_value, settings.autoConvertTxtToMd)
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
      case 'ai.providers':
        settings.aiProviders = normalizeAiProviders(item.setting_value)
        break
      case 'ai.active_provider_id':
        settings.activeAiProviderId = toStringOrNull(item.setting_value)
        break
      case 'backup.git_enabled':
        settings.backupGitEnabled = toBoolean(item.setting_value, settings.backupGitEnabled)
        break
    }
  })

  if (
    settings.activeAiProviderId &&
    !settings.aiProviders.some((provider) => provider.id === settings.activeAiProviderId)
  ) {
    settings.activeAiProviderId = settings.aiProviders.find((provider) => provider.enabled)?.id ?? null
  }

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
      setting_key: 'document.auto_convert_txt_to_md',
      setting_value: String(settings.autoConvertTxtToMd),
      value_type: 'boolean',
      group_name: 'document',
      description: '上传 txt 文档时是否自动保存为 Markdown',
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
      setting_key: 'ai.providers',
      setting_value: settings.aiProviders.map((provider) => ({
        id: provider.id,
        name: provider.name,
        provider_type: provider.provider_type,
        base_url: provider.base_url,
        api_key: provider.api_key?.trim() || null,
        model_name: provider.model_name,
        enabled: provider.enabled
      })),
      value_type: 'json',
      group_name: 'ai',
      description: 'AI 模型提供方配置列表',
      is_public: 0
    },
    {
      setting_key: 'ai.active_provider_id',
      setting_value: settings.activeAiProviderId,
      value_type: 'string',
      group_name: 'ai',
      description: '当前默认使用的 AI 模型配置',
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
    return normalizeSystemSettings(responses)
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
