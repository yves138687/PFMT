<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Key, Lock, Setting, Switch, Warning } from '@element-plus/icons-vue'

import { useSettingsStore } from '@/stores/settingsStore'
import type { SystemSettings } from '@/types/settings'

const settingsStore = useSettingsStore()
const form = reactive<SystemSettings>({ ...settingsStore.settings })

watch(
  () => settingsStore.settings,
  (settings) => {
    Object.assign(form, settings)
  },
  { immediate: true }
)

async function reloadSettings() {
  await settingsStore.loadSettings()
}

async function saveSettings() {
  if (!form.storageRootPath.trim()) {
    ElMessage.warning('请填写本地存储根路径')
    return
  }

  await settingsStore.saveSettings({ ...form, storageRootPath: form.storageRootPath.trim() })
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
        <h2><el-icon><Key /></el-icon> 预留能力</h2>
      </div>
      <div class="panel-body settings-view__reserved">
        <el-checkbox v-model="form.aiFeatureEnabled">AI 功能入口</el-checkbox>
        <el-checkbox v-model="form.backupGitEnabled">Git 备份入口</el-checkbox>
        <el-alert
          :closable="false"
          type="warning"
          show-icon
          title="AI 与备份属于后续阶段，当前仅保留配置字段，不开放业务链路。"
        >
          <template #icon>
            <el-icon><Warning /></el-icon>
          </template>
        </el-alert>
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

@media (max-width: 720px) {
  .settings-view__help {
    display: block;
    margin: 8px 0 0;
  }
}
</style>
