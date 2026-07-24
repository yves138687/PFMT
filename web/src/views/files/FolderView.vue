<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DocumentAdd, FolderAdd, Refresh, UploadFilled } from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { usePathStore } from '@/stores/pathStore'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileInfo } from '@/types/files'
import { formatDateTime, formatFileSize } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const pathStore = usePathStore()
const settingsStore = useSettingsStore()
const files = ref<FileInfo[]>([])
const loading = ref(false)

const currentPathId = computed(() => (typeof route.params.pathId === 'string' ? route.params.pathId : 'root'))

const selectedPath = computed(() => pathStore.selectedPath)

function buildLogicalAddress(file: FileInfo) {
  const basePath = selectedPath.value.full_path === '/' ? '' : selectedPath.value.full_path.replace(/\/$/, '')
  return `${basePath}/${file.original_name}`
}

function canReadMarkdown(file: FileInfo) {
  return ['.md', '.markdown'].includes((file.file_ext ?? '').toLowerCase()) || file.mime_type === 'text/markdown'
}

function openMarkdown(file: FileInfo) {
  void router.push({
    name: 'markdown',
    params: {
      fileId: file.file_id
    }
  })
}

async function loadFiles() {
  pathStore.selectPath(currentPathId.value)
  loading.value = true
  try {
    files.value = await filesApi.listFiles(currentPathId.value, settingsStore.showHiddenContent)
  } catch {
    files.value = []
  } finally {
    loading.value = false
  }
}

watch(
  [currentPathId, () => settingsStore.showHiddenContent],
  () => {
    void loadFiles()
  },
  { immediate: true }
)
</script>

<template>
  <section class="page-shell folder-view">
    <div class="page-heading">
      <div>
        <h1>{{ selectedPath.path_name }}</h1>
        <p>{{ selectedPath.full_path }}</p>
      </div>
      <div class="folder-view__actions">
        <el-button :icon="FolderAdd">新建目录</el-button>
        <el-button :icon="DocumentAdd">新建文档</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="router.push({ name: 'upload' })">上传</el-button>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>文件列表</h2>
        <div class="folder-view__toolbar">
          <el-button :icon="Refresh" :loading="loading" @click="loadFiles">刷新</el-button>
          <el-segmented :model-value="'list'" :options="['list', 'grid']" disabled />
        </div>
      </div>
      <div class="panel-body">
        <el-table v-loading="loading" :data="files" border empty-text="当前目录暂无文件">
          <el-table-column label="真实文件名" min-width="220">
            <template #default="{ row }">
              <span class="folder-view__file-name">
                <strong>{{ row.original_name }}</strong>
                <small>{{ row.file_id }}</small>
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="file_type" label="文件类型" width="120" />
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="逻辑地址 / 存储对象" min-width="300">
            <template #default="{ row }">
              <span class="folder-view__address">
                <strong>{{ buildLogicalAddress(row) }}</strong>
                <small>对象名：{{ row.storage_object_name }}</small>
              </span>
            </template>
          </el-table-column>
          <el-table-column label="加密" width="90">
            <template #default="{ row }">
              <el-tag :type="row.encryption_enabled ? 'success' : 'info'">
                {{ row.encryption_enabled ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at ?? row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :disabled="!canReadMarkdown(row)" @click="openMarkdown(row)">
                查看 Markdown
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>
  </section>
</template>

<style scoped>
.folder-view__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.folder-view__toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.folder-view__file-name,
.folder-view__address {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.folder-view__file-name strong,
.folder-view__address strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-view__file-name small,
.folder-view__address small {
  overflow: hidden;
  color: var(--pfmt-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
