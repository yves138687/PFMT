<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Document, Refresh } from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const router = useRouter()
const fileIdInput = ref(typeof route.params.fileId === 'string' ? route.params.fileId : '')
const fileName = ref('')
const markdownContent = ref('')
const loading = ref(false)

const renderedContent = computed(() => renderMarkdown(markdownContent.value))

async function loadMarkdown() {
  if (!fileIdInput.value) {
    return
  }

  loading.value = true
  try {
    const response = await filesApi.getMarkdownFile(fileIdInput.value)
    fileName.value = response.original_name
    markdownContent.value = response.content
    await router.replace({
      name: 'markdown',
      params: {
        fileId: response.file_id
      }
    })
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.fileId,
  (fileId) => {
    if (typeof fileId === 'string' && fileId !== fileIdInput.value) {
      fileIdInput.value = fileId
      void loadMarkdown()
    }
  },
  { immediate: true }
)
</script>

<template>
  <section class="page-shell markdown-view">
    <div class="page-heading">
      <div>
        <h1>Markdown 查看</h1>
        <p>输入已上传 Markdown 文件的 file_id，读取后进行只读安全渲染。</p>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>文件读取</h2>
      </div>
      <div class="panel-body markdown-view__loader">
        <el-input v-model="fileIdInput" placeholder="请输入 file_id，例如 file_..." clearable @keyup.enter="loadMarkdown">
          <template #prefix>
            <el-icon><Document /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadMarkdown">读取</el-button>
      </div>
    </section>

    <section class="work-panel">
      <div class="panel-header">
        <h2>{{ fileName || '预览内容' }}</h2>
        <span class="muted">只读查看</span>
      </div>
      <div class="panel-body">
        <article v-if="markdownContent" class="markdown-body" v-html="renderedContent" />
        <el-empty v-else description="暂无 Markdown 内容" />
      </div>
    </section>
  </section>
</template>

<style scoped>
.markdown-view {
  display: grid;
  gap: 16px;
}

.markdown-view__loader {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
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

@media (max-width: 560px) {
  .markdown-view__loader {
    grid-template-columns: 1fr;
  }
}
</style>
