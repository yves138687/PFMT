<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Key, Lock, Plus, Setting, Switch } from '@element-plus/icons-vue'

import { useSettingsStore } from '@/stores/settingsStore'
import type { AiProviderConfig, AiProviderType, SystemSettings } from '@/types/settings'

const settingsStore = useSettingsStore()

const providerTypeOptions: Array<{ label: string; value: AiProviderType }> = [
  { label: 'OpenAI Compatible', value: 'openai_compatible' },
  { label: 'Ollama', value: 'ollama' },
  { label: '自定义', value: 'custom' }
]

function cloneSettings(settings: SystemSettings): SystemSettings {
  return {
    ...settings,
    aiProviders: settings.aiProviders.map((provider) => ({ ...provider, api_key: null }))
  }
}

const form = reactive<SystemSettings>(cloneSettings(settingsStore.settings))

const enabledProviderOptions = computed(() =>
  form.aiProviders
    .filter((provider) => provider.enabled)
    .map((provider) => ({
      label: `${provider.name || '未命名模型'} / ${provider.model_name || '未填写模型'}`,
      value: provider.id
    }))
)

watch(
  () => settingsStore.settings,
  (settings) => {
    Object.assign(form, cloneSettings(settings))
  },
  { immediate: true }
)

function createProviderId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID()
  }

  return `ai-provider-${Date.now()}`
}

function addAiProvider() {
  const provider: AiProviderConfig = {
    id: createProviderId(),
    name: 'OpenAI Compatible',
    provider_type: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
    api_key: null,
    api_key_configured: false,
    model_name: '',
    enabled: true
  }

  form.aiProviders.push(provider)
  form.activeAiProviderId = provider.id
}

function removeAiProvider(providerId: string) {
  const index = form.aiProviders.findIndex((provider) => provider.id === providerId)
  if (index === -1) {
    return
  }

  form.aiProviders.splice(index, 1)
  if (form.activeAiProviderId === providerId) {
    form.activeAiProviderId = form.aiProviders.find((provider) => provider.enabled)?.id ?? null
  }
}

function handleProviderEnabledChange(provider: AiProviderConfig) {
  if (!provider.enabled && form.activeAiProviderId === provider.id) {
    form.activeAiProviderId = form.aiProviders.find((item) => item.enabled && item.id !== provider.id)?.id ?? null
  } else if (provider.enabled && !form.activeAiProviderId) {
    form.activeAiProviderId = provider.id
  }
}

async function reloadSettings() {
  await settingsStore.loadSettings()
}

async function saveSettings() {
  if (!form.storageRootPath.trim()) {
    ElMessage.warning('请填写本地存储根路径')
    return
  }

  for (const provider of form.aiProviders) {
    if (!provider.name.trim() || !provider.base_url.trim() || !provider.model_name.trim()) {
      ElMessage.warning('请完整填写 AI 模型名称、API URL 和模型名称')
      return
    }
  }

  if (
    form.activeAiProviderId &&
    !form.aiProviders.some((provider) => provider.enabled && provider.id === form.activeAiProviderId)
  ) {
    form.activeAiProviderId = form.aiProviders.find((provider) => provider.enabled)?.id ?? null
  }

  await settingsStore.saveSettings({
    ...form,
    storageRootPath: form.storageRootPath.trim(),
    aiProviders: form.aiProviders.map((provider) => ({
      ...provider,
      name: provider.name.trim(),
      base_url: provider.base_url.trim(),
      api_key: provider.api_key?.trim() || null,
      model_name: provider.model_name.trim()
    }))
  })
}
</script>

<template>
  <section class="page-shell settings-view">
    <div class="page-heading">
      <div>
        <h1>系统配置</h1>
        <p>配置第一阶段影响上传、加密和隐藏展示的系统级开关。</p>
      </div>
      <div class="settings-view__heading-actions">
        <el-button :loading="settingsStore.loading" @click="reloadSettings">刷新</el-button>
        <el-button type="primary" :loading="settingsStore.saving" @click="saveSettings">保存配置</el-button>
      </div>
    </div>

    <section class="work-panel settings-view__section">
      <div class="panel-header">
        <h2><el-icon><Switch /></el-icon> 基础设置</h2>
      </div>
      <div class="panel-body">
        <el-form label-width="180px">
          <el-form-item label="隐藏功能">
            <el-switch v-model="form.hiddenFeatureEnabled" />
            <span class="settings-view__help">控制系统是否支持隐藏目录和隐藏文件。</span>
          </el-form-item>
        </el-form>
      </div>
    </section>

    <section class="work-panel settings-view__section">
      <div class="panel-header">
        <h2><el-icon><Lock /></el-icon> 加密设置</h2>
      </div>
      <div class="panel-body">
        <el-form label-width="180px">
          <el-form-item label="文件本体加密">
            <el-switch v-model="form.encryptionEnabled" />
            <span class="settings-view__help">上传入口会把该开关作为 encryption_enabled 提交给后端。</span>
          </el-form-item>
          <el-alert
            :closable="false"
            type="info"
            show-icon
            title="密钥派生、随机化存储标识和流式加密由后端实现，前端只展示并传递配置状态。"
          />
        </el-form>
      </div>
    </section>

    <section class="work-panel settings-view__section">
      <div class="panel-header">
        <h2><el-icon><Setting /></el-icon> 存储设置</h2>
      </div>
      <div class="panel-body">
        <el-form label-width="180px">
          <el-form-item label="本地存储根路径" required>
            <el-input v-model="form.storageRootPath" placeholder="storage/data" />
            <span class="settings-view__help">对应 system_setting 中的 storage.local_root。</span>
          </el-form-item>
        </el-form>
      </div>
    </section>

    <section class="work-panel settings-view__section">
      <div class="panel-header">
        <h2><el-icon><Key /></el-icon> AI 设置</h2>
      </div>
      <div class="panel-body">
        <el-form label-width="180px">
          <el-form-item label="AI 功能入口">
            <el-switch v-model="form.aiFeatureEnabled" />
            <span class="settings-view__help">当前只保存模型配置，不开放 AI 使用链路。</span>
          </el-form-item>
          <el-form-item label="默认模型">
            <el-select
              v-model="form.activeAiProviderId"
              clearable
              placeholder="选择要使用的模型"
              class="settings-view__select"
              :disabled="enabledProviderOptions.length === 0"
            >
              <el-option
                v-for="option in enabledProviderOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <span class="settings-view__help">后续 AI 功能会默认使用该模型配置。</span>
          </el-form-item>
        </el-form>

        <div class="settings-view__table-toolbar">
          <strong>模型配置列表</strong>
          <el-button type="primary" :icon="Plus" @click="addAiProvider">新增配置</el-button>
        </div>

        <el-table :data="form.aiProviders" border class="settings-view__provider-table">
          <el-table-column label="启用" width="86">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="handleProviderEnabledChange(row)" />
            </template>
          </el-table-column>
          <el-table-column label="名称" min-width="170">
            <template #default="{ row }">
              <el-input v-model="row.name" placeholder="OpenAI 主模型" />
            </template>
          </el-table-column>
          <el-table-column label="接口类型" min-width="170">
            <template #default="{ row }">
              <el-select v-model="row.provider_type" class="settings-view__cell-control">
                <el-option
                  v-for="option in providerTypeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="API URL" min-width="240">
            <template #default="{ row }">
              <el-input v-model="row.base_url" placeholder="https://api.openai.com/v1" />
            </template>
          </el-table-column>
          <el-table-column label="模型名称" min-width="180">
            <template #default="{ row }">
              <el-input v-model="row.model_name" placeholder="gpt-4.1" />
            </template>
          </el-table-column>
          <el-table-column label="API Key" min-width="220">
            <template #default="{ row }">
              <div class="settings-view__key-cell">
                <el-input v-model="row.api_key" type="password" show-password placeholder="留空则不覆盖" />
                <el-tag size="small" :type="row.api_key_configured ? 'success' : 'info'">
                  {{ row.api_key_configured ? '已配置' : '未配置' }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="默认" width="86">
            <template #default="{ row }">
              <el-radio
                v-model="form.activeAiProviderId"
                :label="row.id"
                :disabled="!row.enabled"
              >
                使用
              </el-radio>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="86">
            <template #default="{ row }">
              <el-button :icon="Delete" circle @click="removeAiProvider(row.id)" />
            </template>
          </el-table-column>
        </el-table>

        <el-empty
          v-if="form.aiProviders.length === 0"
          description="暂无 AI 模型配置"
          :image-size="80"
        />
      </div>
    </section>

    <section class="work-panel settings-view__section">
      <div class="panel-header">
        <h2><el-icon><Key /></el-icon> 预留能力</h2>
      </div>
      <div class="panel-body settings-view__reserved">
        <el-checkbox v-model="form.backupGitEnabled">Git 备份入口</el-checkbox>
      </div>
    </section>
  </section>
</template>

<style scoped>
.settings-view__heading-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.settings-view__section {
  margin-bottom: 16px;
}

.settings-view__section h2 {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.settings-view__help {
  margin-left: 12px;
  color: var(--pfmt-text-muted);
  font-size: 13px;
}

.settings-view__reserved {
  display: grid;
  gap: 12px;
}

.settings-view__select {
  max-width: 420px;
  width: 100%;
}

.settings-view__table-toolbar {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  margin-bottom: 12px;
}

.settings-view__provider-table {
  width: 100%;
}

.settings-view__cell-control {
  width: 100%;
}

.settings-view__key-cell {
  align-items: center;
  display: grid;
  gap: 8px;
  grid-template-columns: minmax(150px, 1fr) auto;
}

@media (max-width: 720px) {
  .settings-view__help {
    display: block;
    margin: 8px 0 0;
  }

  .settings-view__key-cell {
    grid-template-columns: 1fr;
  }
}
</style>
