<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { Delete, Edit, Plus, Refresh, Search, Upload, View } from '@element-plus/icons-vue'

import { tagsApi } from '@/api/files'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileDetail, FileTag, TagImportDelimiter } from '@/types/files'
import { formatDateTime, formatFileSize } from '@/utils/format'

type TagFilterMode = 'all' | 'used' | 'unused'
type TagSortMode = 'usage_desc' | 'name_asc' | 'name_desc'

interface ImportPreview {
  valid: string[]
  duplicateCount: number
  invalid: string[]
  existingCount: number
}

const router = useRouter()
const settingsStore = useSettingsStore()
const tags = ref<FileTag[]>([])
const selectedTag = ref<FileTag | null>(null)
const tagFiles = ref<FileDetail[]>([])
const loading = ref(false)
const filesLoading = ref(false)
const saving = ref(false)
const importLoading = ref(false)
const keyword = ref('')
const fileKeyword = ref('')
const filterMode = ref<TagFilterMode>('all')
const sortMode = ref<TagSortMode>('usage_desc')
const createForm = ref({ tag_name: '', tag_color: '' })
const editVisible = ref(false)
const editForm = ref({ tag_id: '', tag_name: '', tag_color: '' })
const importVisible = ref(false)
const importForm = ref<{
  raw_text: string
  delimiter: TagImportDelimiter
  custom_delimiter: string
}>({
  raw_text: '',
  delimiter: 'newline',
  custom_delimiter: ''
})

const delimiterOptions: Array<{ label: string, value: TagImportDelimiter, hint: string }> = [
  { label: '换行', value: 'newline', hint: '\\n' },
  { label: '中文逗号', value: 'comma_cn', hint: '，' },
  { label: '英文逗号', value: 'comma_en', hint: ',' },
  { label: '井号', value: 'hash', hint: '#' },
  { label: '斜杠', value: 'slash', hint: '/' },
  { label: '分号', value: 'semicolon', hint: ';' },
  { label: '自定义', value: 'custom', hint: '自定义' }
]

const totalUsedCount = computed(() => tags.value.filter((tag) => (tag.file_count ?? 0) > 0).length)
const totalFileRelations = computed(() => tags.value.reduce((sum, tag) => sum + (tag.file_count ?? 0), 0))
const maxFileCount = computed(() => Math.max(1, ...tags.value.map((tag) => tag.file_count ?? 0)))

const filteredTags = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  return tags.value
    .filter((tag) => {
      const count = tag.file_count ?? 0
      const matchesKeyword = !normalizedKeyword || tag.tag_name.toLowerCase().includes(normalizedKeyword)
      const matchesFilter =
        filterMode.value === 'all' ||
        (filterMode.value === 'used' && count > 0) ||
        (filterMode.value === 'unused' && count === 0)
      return matchesKeyword && matchesFilter
    })
    .sort((left, right) => {
      if (sortMode.value === 'name_asc') {
        return left.tag_name.localeCompare(right.tag_name)
      }
      if (sortMode.value === 'name_desc') {
        return right.tag_name.localeCompare(left.tag_name)
      }
      return (right.file_count ?? 0) - (left.file_count ?? 0) || left.tag_name.localeCompare(right.tag_name)
    })
})

const filteredTagFiles = computed(() => {
  const normalizedKeyword = fileKeyword.value.trim().toLowerCase()
  if (!normalizedKeyword) {
    return tagFiles.value
  }
  return tagFiles.value.filter((file) => {
    const content = [
      file.original_name,
      file.logical_path,
      file.remark,
      file.summary_content,
      ...(file.tags ?? []).map((tag) => tag.tag_name)
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return content.includes(normalizedKeyword)
  })
})

const importPreview = computed<ImportPreview>(() => {
  const delimiter = resolveDelimiter()
  if (!delimiter) {
    return { valid: [], duplicateCount: 0, invalid: [], existingCount: 0 }
  }
  const existingNames = new Set(tags.value.map((tag) => tag.tag_name.toLowerCase()))
  const seen = new Set<string>()
  const valid: string[] = []
  const invalid: string[] = []
  let duplicateCount = 0
  let existingCount = 0
  importForm.value.raw_text.split(delimiter).forEach((item) => {
    const tagName = item.trim()
    if (!tagName) {
      return
    }
    if (tagName.length > 128) {
      invalid.push(tagName)
      return
    }
    const lowered = tagName.toLowerCase()
    if (seen.has(lowered)) {
      duplicateCount += 1
      return
    }
    seen.add(lowered)
    if (existingNames.has(lowered)) {
      existingCount += 1
    }
    valid.push(tagName)
  })
  return { valid, duplicateCount, invalid, existingCount }
})

async function loadTags() {
  loading.value = true
  try {
    tags.value = await tagsApi.listTags({ withUsage: true, includeUnused: true })
    if (selectedTag.value && !tags.value.some((tag) => tag.tag_id === selectedTag.value?.tag_id)) {
      selectedTag.value = null
      tagFiles.value = []
    } else if (selectedTag.value) {
      selectedTag.value = tags.value.find((tag) => tag.tag_id === selectedTag.value?.tag_id) ?? selectedTag.value
    }
  } finally {
    loading.value = false
  }
}

async function selectTag(tag: FileTag) {
  selectedTag.value = tag
  fileKeyword.value = ''
  await loadTagFiles(tag)
}

async function loadTagFiles(tag = selectedTag.value) {
  if (!tag) {
    tagFiles.value = []
    return
  }
  filesLoading.value = true
  try {
    const response = await tagsApi.listTagFiles(tag.tag_id)
    tagFiles.value = response.items
  } finally {
    filesLoading.value = false
  }
}

async function createTag() {
  const tagName = createForm.value.tag_name.trim()
  if (!tagName) {
    return
  }
  saving.value = true
  try {
    await tagsApi.createTag(tagName, createForm.value.tag_color || null)
    createForm.value = { tag_name: '', tag_color: '' }
    ElMessage.success('标签已创建')
    await loadTags()
  } finally {
    saving.value = false
  }
}

function openEditTag(tag: FileTag) {
  editForm.value = {
    tag_id: tag.tag_id,
    tag_name: tag.tag_name,
    tag_color: tag.tag_color ?? ''
  }
  editVisible.value = true
}

async function saveEditTag() {
  const tagName = editForm.value.tag_name.trim()
  if (!tagName) {
    return
  }
  saving.value = true
  try {
    const updated = await tagsApi.updateTag(editForm.value.tag_id, {
      tag_name: tagName,
      tag_color: editForm.value.tag_color || null
    })
    ElMessage.success('标签已更新')
    editVisible.value = false
    await loadTags()
    if (selectedTag.value?.tag_id === updated.tag_id) {
      selectedTag.value = tags.value.find((tag) => tag.tag_id === updated.tag_id) ?? updated
    }
  } finally {
    saving.value = false
  }
}

async function deleteTag(tag: FileTag) {
  const count = tag.file_count ?? 0
  const message = count > 0
    ? `将删除标签“${tag.tag_name}”，并移除当前可见及已授权范围内的文章关联。`
    : `将删除未使用标签“${tag.tag_name}”。`
  await ElMessageBox.confirm(message, '删除标签', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
  await tagsApi.deleteTag(tag.tag_id)
  ElMessage.success('标签已删除')
  if (selectedTag.value?.tag_id === tag.tag_id) {
    selectedTag.value = null
    tagFiles.value = []
  }
  await loadTags()
}

function openImportDialog() {
  importForm.value = {
    raw_text: '',
    delimiter: 'newline',
    custom_delimiter: ''
  }
  importVisible.value = true
}

async function importTags() {
  const preview = importPreview.value
  if (!preview.valid.length) {
    ElMessage.warning('没有可导入的标签')
    return
  }
  if (preview.invalid.length) {
    ElMessage.warning('存在超长标签，请调整后再导入')
    return
  }
  importLoading.value = true
  try {
    const response = await tagsApi.importTags({
      raw_text: importForm.value.raw_text,
      delimiter: importForm.value.delimiter,
      custom_delimiter: importForm.value.delimiter === 'custom' ? importForm.value.custom_delimiter : null
    })
    ElMessage.success(`导入完成：新增 ${response.total_created} 个，复用 ${response.total_reused} 个`)
    importVisible.value = false
    await loadTags()
  } finally {
    importLoading.value = false
  }
}

function resolveDelimiter() {
  const option = delimiterOptions.find((item) => item.value === importForm.value.delimiter)
  if (importForm.value.delimiter === 'custom') {
    return importForm.value.custom_delimiter || ''
  }
  return option?.hint === '\\n' ? '\n' : option?.hint ?? ''
}

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

function tagRate(tag: FileTag) {
  return Math.round(((tag.file_count ?? 0) / maxFileCount.value) * 100)
}

function tagNames(file: FileDetail) {
  return (file.tags ?? []).map((tag) => tag.tag_name).join('、')
}

onMounted(() => {
  void loadTags()
})

watch(
  () => settingsStore.showHiddenContent,
  async () => {
    await loadTags()
    await loadTagFiles()
  }
)
</script>

<template>
  <section class="page-shell tags-view">
    <div class="page-heading">
      <div>
        <h1>标签管理</h1>
        <p>管理全局标签，并按当前会话可见范围查看标签关联文章。</p>
      </div>
      <div class="tags-view__heading-actions">
        <el-button :icon="Upload" @click="openImportDialog">批量导入</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadTags">刷新</el-button>
      </div>
    </div>

    <div class="tags-view__stats">
      <div>
        <span>标签总数</span>
        <strong>{{ tags.length }}</strong>
      </div>
      <div>
        <span>已使用</span>
        <strong>{{ totalUsedCount }}</strong>
      </div>
      <div>
        <span>可见文章关联</span>
        <strong>{{ totalFileRelations }}</strong>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-body tags-view__create">
        <el-input v-model="createForm.tag_name" placeholder="新建标签" clearable @keyup.enter="createTag" />
        <el-color-picker v-model="createForm.tag_color" />
        <el-button type="primary" :icon="Plus" :loading="saving" @click="createTag">新建</el-button>
      </div>
    </section>

    <div class="tags-view__workspace">
      <section class="work-panel tags-view__list-panel">
        <div class="panel-header tags-view__toolbar">
          <el-input v-model="keyword" placeholder="搜索标签" clearable>
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-select v-model="filterMode" class="tags-view__small-select">
            <el-option label="全部" value="all" />
            <el-option label="已使用" value="used" />
            <el-option label="未使用" value="unused" />
          </el-select>
          <el-select v-model="sortMode" class="tags-view__small-select">
            <el-option label="使用量" value="usage_desc" />
            <el-option label="名称正序" value="name_asc" />
            <el-option label="名称倒序" value="name_desc" />
          </el-select>
        </div>
        <div v-loading="loading" class="panel-body tags-view__tag-list">
          <button
            v-for="tag in filteredTags"
            :key="tag.tag_id"
            class="tags-view__tag-row"
            :class="{ 'tags-view__tag-row--active': selectedTag?.tag_id === tag.tag_id }"
            type="button"
            @click="selectTag(tag)"
          >
            <span class="tags-view__tag-main">
              <span class="tags-view__swatch" :style="{ backgroundColor: tag.tag_color || '#94a3b8' }" />
              <strong>{{ tag.tag_name }}</strong>
              <small>{{ tag.file_count ?? 0 }} 篇文章</small>
            </span>
            <span class="tags-view__usage">
              <span :style="{ width: `${tagRate(tag)}%` }" />
            </span>
            <span class="tags-view__row-actions" @click.stop>
              <el-button text circle :icon="Edit" :aria-label="`编辑${tag.tag_name}`" @click="openEditTag(tag)" />
              <el-button text circle :icon="Delete" :aria-label="`删除${tag.tag_name}`" @click="deleteTag(tag)" />
            </span>
          </button>
          <el-empty v-if="!filteredTags.length && !loading" description="暂无标签" />
        </div>
      </section>

      <section class="work-panel tags-view__files-panel">
        <div class="panel-header tags-view__files-header">
          <div>
            <h2>{{ selectedTag ? selectedTag.tag_name : '关联文章' }}</h2>
            <span class="muted">{{ selectedTag ? `${tagFiles.length} 篇可见文章` : '选择左侧标签后查看文章' }}</span>
          </div>
          <el-input v-model="fileKeyword" class="tags-view__file-search" placeholder="筛选文章" clearable />
        </div>
        <div class="panel-body">
          <el-table v-loading="filesLoading" :data="filteredTagFiles" border empty-text="暂无关联文章">
            <el-table-column label="文件" min-width="260">
              <template #default="{ row }">
                <span class="tags-view__file">
                  <strong>{{ row.original_name }}</strong>
                  <small>{{ row.logical_path }}</small>
                  <small v-if="row.remark || row.summary_content">{{ row.remark || row.summary_content }}</small>
                  <small v-if="row.tags?.length">{{ tagNames(row) }}</small>
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="file_type" label="类型" width="100" />
            <el-table-column label="大小" width="120">
              <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
            </el-table-column>
            <el-table-column label="更新时间" width="180">
              <template #default="{ row }">{{ formatDateTime(row.updated_at ?? row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="92" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :icon="View" @click="openFile(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>

    <el-dialog v-model="editVisible" title="编辑标签" width="420px">
      <el-form label-position="top">
        <el-form-item label="标签名">
          <el-input v-model="editForm.tag_name" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="editForm.tag_color" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEditTag">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="批量导入标签" width="640px" class="tags-view__import-dialog">
      <el-form label-position="top">
        <el-form-item label="导入内容">
          <el-input
            v-model="importForm.raw_text"
            type="textarea"
            :rows="8"
            placeholder="输入标签文本，例如：合同，项目，归档"
          />
        </el-form-item>
        <el-form-item label="分隔符">
          <el-segmented
            v-model="importForm.delimiter"
            :options="delimiterOptions.map((item) => ({ label: item.label, value: item.value }))"
          />
        </el-form-item>
        <el-form-item v-if="importForm.delimiter === 'custom'" label="自定义分隔符">
          <el-input v-model="importForm.custom_delimiter" maxlength="16" placeholder="输入分隔字符" />
        </el-form-item>
      </el-form>
      <div class="tags-view__import-preview">
        <span>将导入 {{ importPreview.valid.length }} 个</span>
        <span>重复 {{ importPreview.duplicateCount }} 个</span>
        <span>已存在 {{ importPreview.existingCount }} 个</span>
        <span>无效 {{ importPreview.invalid.length }} 个</span>
      </div>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" @click="importTags">确认导入</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.tags-view {
  display: grid;
  gap: 16px;
}

.tags-view__heading-actions,
.tags-view__create,
.tags-view__toolbar,
.tags-view__files-header,
.tags-view__import-preview {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tags-view__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.tags-view__stats div {
  padding: 14px 16px;
  border: 1px solid var(--pfmt-border-soft);
  border-radius: 8px;
  background: var(--pfmt-surface);
}

.tags-view__stats span {
  display: block;
  color: var(--pfmt-text-muted);
  font-size: 13px;
}

.tags-view__stats strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
}

.tags-view__create {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
}

.tags-view__workspace {
  display: grid;
  grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.tags-view__toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 112px 118px;
}

.tags-view__small-select {
  width: 100%;
}

.tags-view__tag-list {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 360px);
  min-height: 360px;
  overflow: auto;
}

.tags-view__tag-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 72px auto;
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--pfmt-border-soft);
  border-radius: 8px;
  background: #ffffff;
  color: var(--pfmt-text);
  text-align: left;
  cursor: pointer;
}

.tags-view__tag-row--active {
  border-color: var(--pfmt-primary);
  background: var(--pfmt-primary-soft);
}

.tags-view__tag-main {
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr);
  column-gap: 8px;
  row-gap: 2px;
  align-items: center;
  min-width: 0;
}

.tags-view__swatch {
  width: 14px;
  height: 14px;
  border-radius: 4px;
}

.tags-view__tag-main strong,
.tags-view__tag-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tags-view__tag-main small {
  grid-column: 2;
  color: var(--pfmt-text-muted);
  font-size: 12px;
}

.tags-view__usage {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--pfmt-border-soft);
}

.tags-view__usage span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--pfmt-primary);
}

.tags-view__row-actions {
  display: inline-flex;
  gap: 2px;
}

.tags-view__files-header {
  justify-content: space-between;
}

.tags-view__files-header h2 {
  margin: 0 0 4px;
  font-size: 16px;
}

.tags-view__file-search {
  width: 220px;
}

.tags-view__file {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.tags-view__file strong,
.tags-view__file small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tags-view__file small {
  color: var(--pfmt-text-muted);
}

.tags-view__import-preview {
  flex-wrap: wrap;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--pfmt-bg);
  color: var(--pfmt-text-muted);
  font-size: 13px;
}

@media (max-width: 980px) {
  .tags-view__workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .tags-view__tag-list {
    max-height: none;
    min-height: 0;
  }
}

@media (max-width: 640px) {
  .tags-view__heading-actions,
  .tags-view__files-header {
    align-items: stretch;
    flex-direction: column;
  }

  .tags-view__stats,
  .tags-view__create,
  .tags-view__toolbar {
    grid-template-columns: minmax(0, 1fr);
  }

  .tags-view__file-search {
    width: 100%;
  }

  .tags-view__tag-row {
    grid-template-columns: minmax(0, 1fr) 64px auto;
  }
}
</style>
