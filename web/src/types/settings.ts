/** system_setting.value_type 支持的值类型。 */
export type SettingValueType = 'string' | 'boolean' | 'number' | 'json'

/** 前端已知的系统配置键，允许后端继续返回自定义配置键。 */
export type SystemSettingKey =
  | 'storage.encryption_enabled'
  | 'storage.local_root'
  | 'storage.local_root_path'
  | 'document.auto_convert_txt_to_md'
  | 'hidden.feature_enabled'
  | 'hidden.show_hidden_default'
  | 'hidden.verify_password_hash'
  | 'hidden.verify_password_required'
  | 'ai.feature_enabled'
  | 'ai.providers'
  | 'ai.active_provider_id'
  | 'backup.git_enabled'

/** AI 模型接口类型；仅作为配置和后续 adapter 路由提示。 */
export type AiProviderType = 'openai_compatible' | 'ollama' | 'custom'

/** AI 模型提供方配置，api_key 保存后只允许以后端脱敏状态回显。 */
export interface AiProviderConfig {
  /** 稳定配置 ID，用于默认模型选择和后续调用路由。 */
  id: string
  /** 用户自定义配置名称。 */
  name: string
  /** 通用接口类型。 */
  provider_type: AiProviderType
  /** OpenAI Compatible API URL 或本地模型服务地址。 */
  base_url: string
  /** 新输入的 API Key；保存后前端应清空。 */
  api_key?: string | null
  /** 后端脱敏返回的密钥配置状态。 */
  api_key_configured?: boolean
  /** 要调用的模型名称。 */
  model_name: string
  /** 是否允许作为可选模型。 */
  enabled: boolean
}

/** 后端系统配置项 DTO，setting_value 会按 value_type 转成业务值。 */
export interface SystemSettingDto {
  setting_key: SystemSettingKey | string
  setting_value: string | number | boolean | AiProviderConfig[] | null
  value_type: SettingValueType
  group_name: 'storage' | 'hidden' | 'ai' | 'backup' | string
  description?: string | null
  is_public?: boolean | number
  updated_at?: string
}

/** 前端配置列表项，统一把 is_public 归一为 boolean。 */
export interface SettingItem extends Omit<SystemSettingDto, 'setting_value' | 'is_public'> {
  setting_value: SystemSettingDto['setting_value']
  is_public: boolean
}

/** 系统配置页使用的视图模型。 */
export interface SystemSettings {
  hiddenFeatureEnabled: boolean
  encryptionEnabled: boolean
  autoConvertTxtToMd: boolean
  showHiddenDefault: boolean
  hiddenVerifyPasswordConfigured: boolean
  hiddenVerifyPasswordRequired: boolean
  storageRootPath: string
  aiFeatureEnabled: boolean
  aiProviders: AiProviderConfig[]
  activeAiProviderId: string | null
  backupGitEnabled: boolean
}

/** 前端在后端配置尚未加载时使用的默认配置。 */
export const DEFAULT_SYSTEM_SETTINGS: SystemSettings = {
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
}
