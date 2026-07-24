export type SettingValueType = 'string' | 'boolean' | 'number' | 'json'

export type SystemSettingKey =
  | 'storage.encryption_enabled'
  | 'storage.local_root'
  | 'storage.local_root_path'
  | 'hidden.feature_enabled'
  | 'hidden.show_hidden_default'
  | 'ai.feature_enabled'
  | 'backup.git_enabled'

export interface SystemSettingDto {
  setting_key: SystemSettingKey | string
  setting_value: string | number | boolean | null
  value_type: SettingValueType
  group_name: 'storage' | 'hidden' | 'ai' | 'backup' | string
  description?: string | null
  is_public?: boolean | number
  updated_at?: string
}

export interface SettingItem extends Omit<SystemSettingDto, 'setting_value' | 'is_public'> {
  setting_value: string | null
  is_public: boolean
}

export interface SettingItem extends Omit<SystemSettingDto, 'setting_value' | 'is_public'> {
  setting_value: string | null
  is_public: boolean
}

export interface SystemSettings {
  hiddenFeatureEnabled: boolean
  encryptionEnabled: boolean
  showHiddenDefault: boolean
  storageRootPath: string
  aiFeatureEnabled: boolean
  backupGitEnabled: boolean
}

export const DEFAULT_SYSTEM_SETTINGS: SystemSettings = {
  hiddenFeatureEnabled: true,
  encryptionEnabled: true,
  showHiddenDefault: false,
  storageRootPath: 'storage/data',
  aiFeatureEnabled: false,
  backupGitEnabled: false
}
