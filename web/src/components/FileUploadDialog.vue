<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { FolderOpened, UploadFilled } from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileInfo } from '@/types/files'
import { formatFileSize } from '@/utils/format'

interface SelectedUploadFile {
  uid: string
  file: File
  relativePath?: string
  status: 'pending' | 'uploading' | 'success' | 'failed'
  result?: FileInfo
}

const props = defineProps<{
  modelValue: boolean
  targetPathId: string
  targetFullPath: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  uploaded: []
}>()

const settingsStore = useSettingsStore()
const fileInputRef = ref<HTMLInputElement>()
const directoryInputRef = ref<HTMLInputElement>()
const selectedFiles = ref<SelectedUploadFile[]>([])
const uploading = ref(false)
const dragActive = ref(false)

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
const encryptionText = computed(() => (settingsStore.encryptionEnabled ? '已启用文件本体加密' : '未启用文件本体加密'))

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

function resetQueue() {
  if (uploading.value) {
    return
  }
  selectedFiles.value = []
  dragActive.value = false
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
      try {
        item.result = await filesApi.uploadFile({
          file: item.file,
          pathId: props.targetPathId,
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
      emit('uploaded')
    }
  } finally {
    uploading.value = false
  }
}

watch(
  () => props.modelValue,
  async (value) => {
    if (value && !settingsStore.initialized) {
      await settingsStore.loadSettings()
    }
  }
)
</script>

<template>
  <el-dialog v-model="visible" title="上传文件" width="760px" :close-on-click-modal="!uploading" @closed="resetQueue">
    <div class="file-upload-dialog__meta">
      <span>上传到：{{ targetFullPath }}</span>
      <el-tag :type="settingsStore.encryptionEnabled ? 'success' : 'warning'">{{ encryptionText }}</el-tag>
    </div>

    <section
      class="file-upload-dialog__dropzone"
      :class="{ 'file-upload-dialog__dropzone--active': dragActive }"
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
      <p>文件会默认上传到当前目录。</p>
      <div class="file-upload-dialog__actions">
        <el-button type="primary" :icon="UploadFilled" @click="chooseFiles">选择文件</el-button>
        <el-button :icon="FolderOpened" @click="chooseDirectory">选择目录</el-button>
      </div>
    </section>

    <div class="file-upload-dialog__queue">
      <el-table v-if="selectedFiles.length" :data="selectedFiles" border max-height="280">
        <el-table-column label="文件名" min-width="240">
          <template #default="{ row }">
            <strong>{{ row.file.name }}</strong>
            <small v-if="row.relativePath">{{ row.relativePath }}</small>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ formatFileSize(row.file.size) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'uploading' ? 'primary' : 'info'"
            >
              {{ row.status === 'pending' ? '待上传' : row.status === 'uploading' ? '上传中' : row.status === 'success' ? '完成' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" :disabled="row.status === 'uploading'" @click="removeFile(row.uid)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="上传队列为空" />
    </div>

    <template #footer>
      <el-button :disabled="uploading" @click="visible = false">关闭</el-button>
      <el-button type="primary" :loading="uploading" :disabled="!selectedFiles.length" @click="uploadAll">开始上传</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.file-upload-dialog__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  color: var(--pfmt-text-muted);
}

.file-upload-dialog__dropzone {
  display: grid;
  place-items: center;
  padding: 28px 18px;
  text-align: center;
  background: var(--pfmt-surface);
  border: 1px dashed #aab8ce;
  border-radius: 8px;
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
}

.file-upload-dialog__dropzone--active {
  border-color: var(--pfmt-primary);
  background: var(--pfmt-primary-soft);
}

.file-upload-dialog__dropzone .el-icon {
  color: var(--pfmt-primary);
  font-size: 34px;
}

.file-upload-dialog__dropzone h2 {
  margin: 10px 0 6px;
  font-size: 17px;
}

.file-upload-dialog__dropzone p {
  margin: 0;
  color: var(--pfmt-text-muted);
}

.file-upload-dialog__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 16px;
}

.file-upload-dialog__queue {
  margin-top: 14px;
}

.file-upload-dialog__queue small {
  display: block;
  margin-top: 4px;
  color: var(--pfmt-text-muted);
}
</style>
