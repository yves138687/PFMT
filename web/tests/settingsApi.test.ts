import { describe, expect, it, vi } from 'vitest'

import { normalizeSystemSettings, settingsApi, systemSettingsToDto } from '@/api/settings'
import { DEFAULT_SYSTEM_SETTINGS } from '@/types/settings'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json'
    }
  })
}

describe('settingsApi AI settings', () => {
  it('normalizes AI provider JSON settings', () => {
    const settings = normalizeSystemSettings([
      {
        setting_key: 'document.auto_convert_txt_to_md',
        setting_value: true,
        value_type: 'boolean',
        group_name: 'document',
        is_public: 1
      },
      {
        setting_key: 'ai.providers',
        setting_value: [
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
        value_type: 'json',
        group_name: 'ai',
        is_public: 0
      },
      {
        setting_key: 'ai.active_provider_id',
        setting_value: 'openai-main',
        value_type: 'string',
        group_name: 'ai',
        is_public: 1
      }
    ])

    expect(settings.aiProviders).toHaveLength(1)
    expect(settings.autoConvertTxtToMd).toBe(true)
    expect(settings.aiProviders[0].api_key).toBeNull()
    expect(settings.aiProviders[0].api_key_configured).toBe(true)
    expect(settings.activeAiProviderId).toBe('openai-main')
  })

  it('serializes AI providers and the active provider id', () => {
    const dto = systemSettingsToDto({
      ...DEFAULT_SYSTEM_SETTINGS,
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
          api_key: '',
          api_key_configured: true,
          model_name: 'gpt-4.1',
          enabled: true
        }
      ],
      activeAiProviderId: 'openai-main',
      backupGitEnabled: false
    })

    const providers = dto.find((item) => item.setting_key === 'ai.providers')
    const autoConvertTxtToMd = dto.find((item) => item.setting_key === 'document.auto_convert_txt_to_md')
    const activeProviderId = dto.find((item) => item.setting_key === 'ai.active_provider_id')

    expect(autoConvertTxtToMd?.setting_value).toBe('false')
    expect(autoConvertTxtToMd?.value_type).toBe('boolean')
    expect(providers?.value_type).toBe('json')
    expect(providers?.setting_value).toEqual([
      expect.objectContaining({
        id: 'openai-main',
        api_key: null,
        model_name: 'gpt-4.1'
      })
    ])
    expect(activeProviderId?.setting_value).toBe('openai-main')
  })

  it('returns backend-masked AI providers after saving settings', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'hidden.feature_enabled',
          setting_value: true,
          value_type: 'boolean',
          group_name: 'hidden',
          is_public: true
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'storage.encryption_enabled',
          setting_value: true,
          value_type: 'boolean',
          group_name: 'storage',
          is_public: true
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'document.auto_convert_txt_to_md',
          setting_value: false,
          value_type: 'boolean',
          group_name: 'document',
          is_public: true
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'hidden.show_hidden_default',
          setting_value: false,
          value_type: 'boolean',
          group_name: 'hidden',
          is_public: false
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'hidden.verify_password_required',
          setting_value: false,
          value_type: 'boolean',
          group_name: 'hidden',
          is_public: true
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'storage.local_root',
          setting_value: 'storage/data',
          value_type: 'string',
          group_name: 'storage',
          is_public: false
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'ai.feature_enabled',
          setting_value: true,
          value_type: 'boolean',
          group_name: 'ai',
          is_public: true
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'ai.providers',
          setting_value: [
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
          value_type: 'json',
          group_name: 'ai',
          is_public: false
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'ai.active_provider_id',
          setting_value: 'openai-main',
          value_type: 'string',
          group_name: 'ai',
          is_public: true
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          setting_key: 'backup.git_enabled',
          setting_value: false,
          value_type: 'boolean',
          group_name: 'backup',
          is_public: true
        })
      )
    vi.stubGlobal('fetch', fetchMock)

    const saved = await settingsApi.updateSettings({
      ...DEFAULT_SYSTEM_SETTINGS,
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

    const providersRequest = JSON.parse((fetchMock.mock.calls[7][1] as RequestInit).body as string)
    expect(providersRequest.setting_value[0].api_key).toBe('sk-secret')
    expect(saved.aiProviders[0].api_key).toBeNull()
    expect(saved.aiProviders[0].api_key_configured).toBe(true)
  })
})


describe('settingsApi hidden content verification', () => {
  it('normalizes hidden verification code status and force switch', () => {
    const settings = normalizeSystemSettings([
      {
        setting_key: 'hidden.verify_password_hash',
        setting_value: true,
        value_type: 'boolean',
        group_name: 'hidden',
        is_public: 0
      },
      {
        setting_key: 'hidden.verify_password_required',
        setting_value: true,
        value_type: 'boolean',
        group_name: 'hidden',
        is_public: 1
      }
    ])

    expect(settings.hiddenVerifyPasswordConfigured).toBe(true)
    expect(settings.hiddenVerifyPasswordRequired).toBe(true)
  })

  it('does not send the verification code hash key when saving settings', () => {
    const dto = systemSettingsToDto({
      ...DEFAULT_SYSTEM_SETTINGS,
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      autoConvertTxtToMd: false,
      showHiddenDefault: false,
      hiddenVerifyPasswordConfigured: true,
      hiddenVerifyPasswordRequired: true,
      storageRootPath: 'storage/data',
      aiFeatureEnabled: false,
      aiProviders: [],
      activeAiProviderId: null,
      backupGitEnabled: false
    })

    const keys = dto.map((item) => item.setting_key)
    expect(keys).not.toContain('hidden.verify_password_hash')
    expect(keys).toContain('hidden.verify_password_required')

    const required = dto.find((item) => item.setting_key === 'hidden.verify_password_required')
    expect(required?.setting_value).toBe('true')
  })
})


describe('settingsApi file encryption key management', () => {
  it('rotates file encryption keys through the dedicated endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        encryption_enabled: true,
        key_configured: true,
        active_key_id: 'key_20260807153022_ab12cd',
        active_key_status: 'active_rotating',
        pending_rotation_count: 3
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const status = await settingsApi.rotateFileEncryptionKey('new-secret-key')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/settings/file-encryption/rotate')
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({
      key: 'new-secret-key'
    })
    expect(status.active_key_id).toBe('key_20260807153022_ab12cd')
    expect(status.pending_rotation_count).toBe(3)
  })
})
