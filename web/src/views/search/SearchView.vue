<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, View } from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileDetail } from '@/types/files'
import { formatDateTime, formatFileSize } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()
const loading = ref(false)
const results = ref<FileDetail[]>([])
const total = ref(0)

const keyword = computed(() => (typeof route.query.q === 'string' ? route.query.q.trim() : ''))

function openFile(file: FileDetail) {
  void router.push({
    name: file.file_type === 'text' ? 'document' : 'file-detail',
    params: {
      fileId: file.file_id
    },
    query: {
      pathId: file.path_id
    }
  })
}

function tagNames(file: FileDetail) {
  return (file.tags ?? []).map((tag) => tag.tag_name).join('、')
}

async function loadResults() {
  if (!keyword.value) {
    results.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const response = await filesApi.searchFiles(keyword.value, settingsStore.showHiddenContent)
    results.value = response.items
    total.value = response.total
  } finally {
    loading.value = false
  }
}

watch(
  [keyword, () => settingsStore.showHiddenContent],
  () => {
    void loadResults()
  },
  { immediate: true }
)
</script>

<template>
  <section class="page-shell search-view">
    <div class="page-heading">
      <div>
        <h1>元数据搜索</h1>
        <p>{{ keyword ? `关键词：${keyword}` : '输入关键词后搜索文件名、备注、摘要、标签和类型' }}</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadResults">刷新</el-button>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>搜索结果</h2>
        <span class="muted">{{ total }} 个结果</span>
      </div>
      <div class="panel-body">
        <el-table v-loading="loading" :data="results" border empty-text="暂无搜索结果">
          <el-table-column label="文件" min-width="260">
            <template #default="{ row }">
              <span class="search-view__file">
                <strong>{{ row.original_name }}</strong>
                <small>{{ row.logical_path }}</small>
                <small v-if="row.tags?.length">{{ tagNames(row) }}</small>
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="file_type" label="类型" width="110" />
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column v-if="settingsStore.showHiddenContent" label="状态" width="90">
            <template #default="{ row }">{{ row.is_hidden ? '隐藏' : '显示' }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at ?? row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="View" @click="openFile(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>
  </section>
</template>

<style scoped>
.search-view {
  display: grid;
  gap: 16px;
}

.search-view__file {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.search-view__file strong,
.search-view__file small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-view__file small {
  color: var(--pfmt-text-muted);
}
</style>
