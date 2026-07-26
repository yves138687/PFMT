import { describe, expect, it, vi } from 'vitest'

import { normalizeSystemSettings, settingsApi, systemSettingsToDto } from '@/api/settings'

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
    expect(settings.aiProviders[0].api_key).toBeNull()
    expect(settings.aiProviders[0].api_key_configured).toBe(true)
    expect(settings.activeAiProviderId).toBe('openai-main')
  })

  it('serializes AI providers and the active provider id', () => {
    const dto = systemSettingsToDto({
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      showHiddenDefault: false,
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
    const activeProviderId = dto.find((item) => item.setting_key === 'ai.active_provider_id')

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
          setting_key: 'hidden.show_hidden_default',
          setting_value: false,
          value_type: 'boolean',
          group_name: 'hidden',
          is_public: false
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
      hiddenFeatureEnabled: true,
      encryptionEnabled: true,
      showHiddenDefault: false,
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

    const providersRequest = JSON.parse((fetchMock.mock.calls[5][1] as RequestInit).body as string)
    expect(providersRequest.setting_value[0].api_key).toBe('sk-secret')
    expect(saved.aiProviders[0].api_key).toBeNull()
    expect(saved.aiProviders[0].api_key_configured).toBe(true)
  })
})
