<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Document, Files, FolderOpened, Key, Refresh, UploadFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { filesApi } from '@/api/files'
import { usePathStore } from '@/stores/pathStore'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileDashboardSummary, FileDetail } from '@/types/files'
import { formatDateTime, formatFileSize } from '@/utils/format'

const router = useRouter()
const pathStore = usePathStore()
const settingsStore = useSettingsStore()
const loading = ref(false)
const loadError = ref('')
const summary = ref<FileDashboardSummary>({
  file_total: 0,
  path_total: 0,
  markdown_total: 0,
  recent_accessed: []
})

const stats = computed(() => [
  { label: '文件总数', value: String(summary.value.file_total), note: '已过滤当前会话不可见内容', icon: Files },
  {
    label: '目录总数',
    value: String(summary.value.path_total || pathStore.tree.length),
    note: '包含根目录及可见子目录',
    icon: FolderOpened
  },
  { label: 'Markdown', value: String(summary.value.markdown_total), note: '按扩展名和 MIME 类型统计', icon: Document },
  {
    label: '加密状态',
    value: settingsStore.encryptionEnabled ? '启用' : '关闭',
    note: '由 storage.encryption_enabled 控制',
    icon: Key
  }
])

const quickActions = [
  { label: '上传文件', name: 'folder', icon: UploadFilled, query: { upload: '1' }, params: { pathId: 'root' } },
  { label: '系统配置', name: 'settings', icon: Key },
  { label: '文件列表', name: 'folder', icon: FolderOpened }
]

async function loadDashboardSummary() {
  loading.value = true
  loadError.value = ''
  try {
    summary.value = await filesApi.getDashboardSummary()
  } catch {
    loadError.value = '首页统计加载失败'
  } finally {
    loading.value = false
  }
}

function openRecentFile(row: FileDetail) {
  void router.push({ name: 'file-detail', params: { fileId: row.file_id } })
}

onMounted(() => {
  void loadDashboardSummary()
})

watch(
  () => settingsStore.showHiddenContent,
  () => {
    void loadDashboardSummary()
  }
)
</script>

<template>
  <section class="page-shell">
    <div class="page-heading">
      <div>
        <h1>首页</h1>
        <p>第一阶段工作台，聚焦登录、配置、上传、目录树和文件详情查看。</p>
      </div>
    </div>

    <div class="dashboard__stats">
      <article v-for="item in stats" :key="item.label" class="dashboard__stat">
        <el-icon><component :is="item.icon" /></el-icon>
        <div>
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.note }}</small>
        </div>
      </article>
    </div>

    <section class="work-panel dashboard__section">
      <div class="panel-header">
        <h2>最近访问</h2>
        <div class="dashboard__section-tools">
          <span class="muted">隐藏内容默认不展示</span>
          <el-button :icon="Refresh" text :loading="loading" @click="loadDashboardSummary">刷新</el-button>
        </div>
      </div>
      <div v-loading="loading" class="panel-body">
        <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false" />
        <el-table
          v-else-if="summary.recent_accessed.length > 0"
          :data="summary.recent_accessed"
          class="dashboard__recent-table"
          @row-click="openRecentFile"
        >
          <el-table-column prop="original_name" label="文件名" min-width="220" show-overflow-tooltip />
          <el-table-column prop="logical_path" label="位置" min-width="260" show-overflow-tooltip />
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              {{ row.file_ext || row.file_type }}
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">
              {{ formatFileSize(row.size_bytes) }}
            </template>
          </el-table-column>
          <el-table-column label="最近访问" width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.last_accessed_at) }}
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无最近访问文件" />
      </div>
    </section>

    <section class="work-panel dashboard__section">
      <div class="panel-header">
        <h2>快捷入口</h2>
      </div>
      <div class="dashboard__actions panel-body">
        <el-button
          v-for="action in quickActions"
          :key="action.name"
          :icon="action.icon"
          type="primary"
          plain
          @click="router.push({ name: action.name, params: action.params, query: action.query })"
        >
          {{ action.label }}
        </el-button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.dashboard__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.dashboard__stat {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding: 16px;
  background: var(--pfmt-surface);
  border: 1px solid var(--pfmt-border-soft);
  border-radius: 8px;
}

.dashboard__stat .el-icon {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  color: var(--pfmt-primary);
  background: var(--pfmt-primary-soft);
  font-size: 21px;
}

.dashboard__stat span,
.dashboard__stat small {
  display: block;
  color: var(--pfmt-text-muted);
}

.dashboard__stat strong {
  display: block;
  margin: 2px 0;
  font-size: 22px;
  line-height: 1.3;
}

.dashboard__stat small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.dashboard__section {
  margin-top: 16px;
}

.dashboard__section-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dashboard__recent-table {
  width: 100%;
}

.dashboard__recent-table :deep(.el-table__row) {
  cursor: pointer;
}

.dashboard__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 1000px) {
  .dashboard__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .dashboard__stats {
    grid-template-columns: 1fr;
  }
}
</style>
