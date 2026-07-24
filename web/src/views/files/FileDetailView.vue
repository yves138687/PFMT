<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, InfoFilled, Refresh } from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import FilePropertiesDialog from '@/components/FilePropertiesDialog.vue'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileDetail } from '@/types/files'
import { formatDateTime, formatFileSize } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()
const detail = ref<FileDetail | null>(null)
const markdownContent = ref('')
const loading = ref(false)
const markdownLoading = ref(false)
const propertiesVisible = ref(false)

const fileId = computed(() => (typeof route.params.fileId === 'string' ? route.params.fileId : ''))
const fromPathId = computed(() => {
  const pathId = route.query.pathId
  return typeof pathId === 'string' ? pathId : undefined
})
const renderedContent = computed(() => renderMarkdown(markdownContent.value))
const canPreviewMarkdown = computed(() => {
  const file = detail.value
  return !!file && (['.md', '.markdown'].includes((file.file_ext ?? '').toLowerCase()) || file.mime_type === 'text/markdown')
})

function backToFolder() {
  void router.push({
    name: 'folder',
    params: {
      pathId: fromPathId.value ?? detail.value?.path_id ?? 'root'
    }
  })
}

async function ensureSettingsLoaded() {
  if (!settingsStore.initialized) {
    await settingsStore.loadSettings()
  }
}

async function loadMarkdown() {
  if (!fileId.value || !canPreviewMarkdown.value) {
    markdownContent.value = ''
    return
  }

  markdownLoading.value = true
  try {
    const response = await filesApi.getMarkdownFile(fileId.value, settingsStore.showHiddenContent)
    markdownContent.value = response.content
  } finally {
    markdownLoading.value = false
  }
}

async function loadFileDetail() {
  if (!fileId.value) {
    detail.value = null
    markdownContent.value = ''
    return
  }

  loading.value = true
  try {
    await ensureSettingsLoaded()
    detail.value = await filesApi.getFileDetail(fileId.value, settingsStore.showHiddenContent)
    await loadMarkdown()
  } finally {
    loading.value = false
  }
}

function handleFileSaved(updatedFile: FileDetail) {
  detail.value = updatedFile
}

watch(
  [fileId, () => settingsStore.showHiddenContent],
  () => {
    void loadFileDetail()
  },
  { immediate: true }
)
</script>

<template>
  <section class="page-shell file-detail-view">
    <div class="page-heading">
      <div>
        <h1>{{ detail?.original_name || '文件详情' }}</h1>
        <p>{{ detail?.logical_path || '正在读取文件详情' }}</p>
      </div>
      <div class="file-detail-view__actions">
        <el-button :icon="ArrowLeft" @click="backToFolder">返回列表</el-button>
        <el-button :icon="InfoFilled" :disabled="!detail" @click="propertiesVisible = true">属性</el-button>
        <el-button :icon="Refresh" :loading="loading || markdownLoading" @click="loadFileDetail">刷新</el-button>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>文件信息</h2>
        <span v-if="detail" class="muted">
          {{ formatFileSize(detail.size_bytes) }} · {{ formatDateTime(detail.updated_at) }}
        </span>
      </div>
      <div v-loading="loading" class="panel-body file-detail-view__summary">
        <template v-if="detail">
          <span>类型：{{ detail.file_type }}</span>
          <span>MIME：{{ detail.mime_type || '-' }}</span>
          <span>备注：{{ detail.remark || '无' }}</span>
        </template>
        <el-empty v-else description="暂无文件详情" />
      </div>
    </section>

    <section class="work-panel">
      <div class="panel-header">
        <h2>预览内容</h2>
        <span class="muted">只读查看</span>
      </div>
      <div v-loading="markdownLoading" class="panel-body file-detail-view__preview">
        <article v-if="markdownContent" class="markdown-body" v-html="renderedContent" />
        <el-empty v-else-if="detail && !canPreviewMarkdown" description="当前文件类型暂不支持预览" />
        <el-empty v-else description="暂无 Markdown 内容" />
      </div>
    </section>

    <FilePropertiesDialog
      v-model="propertiesVisible"
      :file="detail"
      :file-id="fileId"
      :show-hidden="settingsStore.showHiddenContent"
      @saved="handleFileSaved"
    />
  </section>
</template>

<style scoped>
.file-detail-view {
  display: grid;
  gap: 16px;
}

.file-detail-view__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.file-detail-view__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  color: var(--pfmt-text-muted);
}

.file-detail-view__preview {
  min-height: 360px;
}

.markdown-body {
  line-height: 1.75;
  color: var(--pfmt-text);
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 1.2em 0 0.5em;
  line-height: 1.35;
}

.markdown-body :deep(pre) {
  overflow: auto;
  padding: 14px;
  background: #0f172a;
  border-radius: 8px;
  color: #e5edf8;
}

.markdown-body :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: #edf2f7;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
}

.markdown-body :deep(blockquote) {
  margin: 12px 0;
  padding: 4px 14px;
  color: var(--pfmt-text-muted);
  border-left: 3px solid var(--pfmt-border);
}
</style>
