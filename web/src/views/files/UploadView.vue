<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { FolderOpened, UploadFilled } from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { usePathStore } from '@/stores/pathStore'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileInfo } from '@/types/files'
import { formatFileSize } from '@/utils/format'

interface SelectedUploadFile {
  uid: string
  file: File
  relativePath?: string
  status: 'pending' | 'uploading' | 'success' | 'failed'
  targetPathId?: string
  targetFullPath?: string
  result?: FileInfo
}

const router = useRouter()
const settingsStore = useSettingsStore()
const pathStore = usePathStore()
const fileInputRef = ref<HTMLInputElement>()
const directoryInputRef = ref<HTMLInputElement>()
const targetPathId = ref('root')
const selectedFiles = ref<SelectedUploadFile[]>([])
const uploading = ref(false)
const dragActive = ref(false)

const pathOptions = computed(() => {
  const options: Array<{ label: string; value: string; fullPath: string }> = []
  const walk = (nodes = pathStore.tree, prefix = '') => {
    nodes.forEach((node) => {
      options.push({
        label: `${prefix}${node.path_name}`,
        value: node.path_id,
        fullPath: node.full_path
      })
      walk(node.children ?? [], `${prefix}${node.path_name} / `)
    })
  }

  walk()
  return options
})

const selectedTargetPath = computed(
  () => pathOptions.value.find((item) => item.value === targetPathId.value) ?? pathOptions.value[0]
)

const encryptionText = computed(() => (settingsStore.encryptionEnabled ? '已启用文件本体加密' : '未启用文件本体加密'))

function buildLogicalAddress(fileName: string, fullPath = '/') {
  const basePath = fullPath === '/' ? '' : fullPath.replace(/\/$/, '')
  return `${basePath}/${fileName}`
}

function uploadLogicalAddress(item: SelectedUploadFile) {
  return buildLogicalAddress(item.result?.original_name ?? item.file.name, item.targetFullPath ?? selectedTargetPath.value?.fullPath)
}

function canReadMarkdown(fileInfo?: FileInfo) {
  return ['.md', '.markdown'].includes((fileInfo?.file_ext ?? '').toLowerCase()) || fileInfo?.mime_type === 'text/markdown'
}

function openMarkdown(fileInfo: FileInfo) {
  void router.push({
    name: 'markdown',
    params: {
      fileId: fileInfo.file_id
    }
  })
}

function openTargetFolder(item: SelectedUploadFile) {
  void router.push({
    name: 'folder',
    params: {
      pathId: item.result?.path_id ?? item.targetPathId ?? targetPathId.value
    }
  })
}

function addFiles(files: FileList | File[]) {
  Array.from(files).forEach((file) => {
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath
    selectedFiles.value.push({
      uid: `${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
      file,
      relativePath,
      status: 'pending'
    })
  })
}

function chooseFiles() {
  fileInputRef.value?.click()
}

function chooseDirectory() {
  directoryInputRef.value?.click()
}

function handleInputChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) {
    addFiles(input.files)
  }
  input.value = ''
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  dragActive.value = false
  if (event.dataTransfer?.files?.length) {
    addFiles(event.dataTransfer.files)
  }
}

function removeFile(uid: string) {
  selectedFiles.value = selectedFiles.value.filter((item) => item.uid !== uid)
}

async function uploadAll() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }

  uploading.value = true
  try {
    for (const item of selectedFiles.value) {
      if (item.status === 'success') {
        continue
      }

      item.status = 'uploading'
      item.targetPathId = targetPathId.value
      item.targetFullPath = selectedTargetPath.value?.fullPath ?? '/'
      try {
        item.result = await filesApi.uploadFile({
          file: item.file,
          pathId: targetPathId.value,
          relativePath: item.relativePath,
          encryptionEnabled: settingsStore.encryptionEnabled
        })
        item.status = 'success'
      } catch {
        item.status = 'failed'
      }
    }

    if (selectedFiles.value.every((item) => item.status === 'success')) {
      ElMessage.success('文件上传完成')
    }
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  if (!settingsStore.initialized) {
    await settingsStore.loadSettings()
  }
  await pathStore.loadTree(settingsStore.showHiddenContent)
})
</script>

<template>
  <section class="page-shell upload-view">
    <div class="page-heading">
      <div>
        <h1>上传文件</h1>
        <p>选择目标目录后拖拽或选择文件，上传时按系统配置传递加密开关。</p>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>上传设置</h2>
        <el-tag :type="settingsStore.encryptionEnabled ? 'success' : 'warning'">{{ encryptionText }}</el-tag>
      </div>
      <div class="panel-body upload-view__settings">
        <el-form label-width="120px">
          <el-form-item label="目标目录">
            <el-select v-model="targetPathId" filterable class="upload-view__path-select">
              <el-option v-for="item in pathOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </section>

    <section
      class="upload-view__dropzone"
      :class="{ 'upload-view__dropzone--active': dragActive }"
      @dragover.prevent="dragActive = true"
      @dragleave.prevent="dragActive = false"
      @drop="handleDrop"
    >
      <input ref="fileInputRef" class="hidden-input" type="file" multiple @change="handleInputChange" />
      <input
        ref="directoryInputRef"
        class="hidden-input"
        type="file"
        multiple
        webkitdirectory
        directory
        @change="handleInputChange"
      />
      <el-icon><UploadFilled /></el-icon>
      <h2>拖拽文件到这里</h2>
      <p>也可以选择单个/多个文件，或选择本地目录批量加入上传队列。</p>
      <div class="upload-view__drop-actions">
        <el-button type="primary" :icon="UploadFilled" @click="chooseFiles">选择文件</el-button>
        <el-button :icon="FolderOpened" @click="chooseDirectory">选择目录</el-button>
      </div>
    </section>

    <section class="work-panel upload-view__queue">
      <div class="panel-header">
        <h2>上传队列</h2>
        <el-button type="primary" :loading="uploading" :disabled="!selectedFiles.length" @click="uploadAll">开始上传</el-button>
      </div>
      <div class="panel-body">
        <el-table v-if="selectedFiles.length" :data="selectedFiles" border>
          <el-table-column label="文件名" min-width="220">
            <template #default="{ row }">
              <strong>{{ row.file.name }}</strong>
              <small v-if="row.relativePath">{{ row.relativePath }}</small>
              <small v-if="row.result">文件 ID：{{ row.result.file_id }}</small>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatFileSize(row.file.size) }}</template>
          </el-table-column>
          <el-table-column label="逻辑地址 / 存储对象" min-width="300">
            <template #default="{ row }">
              <span v-if="row.result" class="upload-view__address">
                <strong>{{ uploadLogicalAddress(row) }}</strong>
                <small>对象名：{{ row.result.storage_object_name }}</small>
              </span>
              <span v-else class="upload-view__empty">上传完成后显示</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag
                :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'uploading' ? 'primary' : 'info'"
              >
                {{ row.status === 'pending' ? '待上传' : row.status === 'uploading' ? '上传中' : row.status === 'success' ? '完成' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.result" link type="primary" @click="openTargetFolder(row)">打开目录</el-button>
              <el-button
                v-if="row.result && canReadMarkdown(row.result)"
                link
                type="primary"
                @click="openMarkdown(row.result)"
              >
                查看
              </el-button>
              <el-button link type="danger" :disabled="row.status === 'uploading'" @click="removeFile(row.uid)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="上传队列为空" />
      </div>
    </section>
  </section>
</template>

<style scoped>
.upload-view {
  display: grid;
  gap: 16px;
}

.upload-view__settings {
  max-width: 680px;
}

.upload-view__path-select {
  width: min(100%, 460px);
}

.upload-view__dropzone {
  display: grid;
  place-items: center;
  padding: 38px 18px;
  text-align: center;
  background: var(--pfmt-surface);
  border: 1px dashed #aab8ce;
  border-radius: 8px;
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
}

.upload-view__dropzone--active {
  border-color: var(--pfmt-primary);
  background: var(--pfmt-primary-soft);
}

.upload-view__dropzone .el-icon {
  color: var(--pfmt-primary);
  font-size: 38px;
}

.upload-view__dropzone h2 {
  margin: 10px 0 6px;
  font-size: 18px;
}

.upload-view__dropzone p {
  margin: 0;
  color: var(--pfmt-text-muted);
}

.upload-view__drop-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 18px;
}

.upload-view__queue small {
  display: block;
  margin-top: 4px;
  color: var(--pfmt-text-muted);
}

.upload-view__address {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.upload-view__address strong,
.upload-view__address small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-view__address small,
.upload-view__empty {
  color: var(--pfmt-text-muted);
}
</style>
