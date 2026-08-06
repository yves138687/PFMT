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
const conflictStrategy = ref<'rename' | 'overwrite'>('rename')
let uploadUidSeed = 0

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
const encryptionText = computed(() => (settingsStore.encryptionEnabled ? '已启用文件本体加密' : '未启用文件本体加密'))
const fileInputId = createUploadId('pfmt-file-upload')
const directoryInputId = createUploadId('pfmt-directory-upload')
const txtConvertText = computed(() => (settingsStore.autoConvertTxtToMd ? 'TXT 将自动转为 Markdown' : 'TXT 保持原格式'))

function createUploadId(prefix: string) {
  uploadUidSeed += 1
  if (globalThis.crypto?.randomUUID) {
    return `${prefix}-${globalThis.crypto.randomUUID()}`
  }

  return `${prefix}-${Date.now()}-${uploadUidSeed}-${Math.random().toString(36).slice(2)}`
}

function uploadStatusText(status: SelectedUploadFile['status']) {
  if (status === 'uploading') {
    return '上传中'
  }
  if (status === 'success') {
    return '完成'
  }
  if (status === 'failed') {
    return '失败'
  }
  return '待上传'
}

function uploadStatusType(status: SelectedUploadFile['status']) {
  if (status === 'success') {
    return 'success'
  }
  if (status === 'failed') {
    return 'danger'
  }
  if (status === 'uploading') {
    return 'primary'
  }
  return 'info'
}

function addFiles(files: FileList | File[]) {
  Array.from(files).forEach((file) => {
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath
    selectedFiles.value.push({
      uid: `${file.name}-${file.size}-${file.lastModified}-${createUploadId('upload-file')}`,
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
          encryptionEnabled: settingsStore.encryptionEnabled,
          conflictStrategy: conflictStrategy.value
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
  <el-dialog
    v-model="visible"
    class="file-upload-dialog"
    title="上传文件"
    width="min(760px, calc(100vw - 24px))"
    :close-on-click-modal="false"
    :close-on-press-escape="!uploading"
    @closed="resetQueue"
  >
    <div class="file-upload-dialog__meta">
      <span>上传到：{{ targetFullPath }}</span>
      <el-tag :type="settingsStore.encryptionEnabled ? 'success' : 'warning'">{{ encryptionText }}</el-tag>
      <el-tag :type="settingsStore.autoConvertTxtToMd ? 'success' : 'info'">{{ txtConvertText }}</el-tag>
    </div>

    <div class="file-upload-dialog__conflict">
      <span>重名文件：</span>
      <el-radio-group v-model="conflictStrategy" :disabled="uploading" size="small">
        <el-radio-button label="rename">自动重命名</el-radio-button>
        <el-radio-button label="overwrite">覆盖已有文件</el-radio-button>
      </el-radio-group>
    </div>

    <section
      class="file-upload-dialog__dropzone"
      :class="{ 'file-upload-dialog__dropzone--active': dragActive }"
      @dragover.prevent="dragActive = true"
      @dragleave.prevent="dragActive = false"
      @drop="handleDrop"
    >
      <input
        :id="fileInputId"
        ref="fileInputRef"
        class="file-upload-dialog__input"
        type="file"
        multiple
        @change="handleInputChange"
      />
      <input
        :id="directoryInputId"
        ref="directoryInputRef"
        class="file-upload-dialog__input"
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
        <label
          class="file-upload-dialog__picker file-upload-dialog__picker--primary"
          :for="fileInputId"
          role="button"
          tabindex="0"
          @keydown.enter.prevent="chooseFiles"
          @keydown.space.prevent="chooseFiles"
        >
          <el-icon><UploadFilled /></el-icon>
          <span>选择文件</span>
        </label>
        <label
          class="file-upload-dialog__picker"
          :for="directoryInputId"
          role="button"
          tabindex="0"
          @keydown.enter.prevent="chooseDirectory"
          @keydown.space.prevent="chooseDirectory"
        >
          <el-icon><FolderOpened /></el-icon>
          <span>选择目录</span>
        </label>
      </div>
    </section>

    <div class="file-upload-dialog__queue">
      <template v-if="selectedFiles.length">
        <el-table class="file-upload-dialog__queue-table" :data="selectedFiles" border max-height="280">
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
              <el-tag :type="uploadStatusType(row.status)">
                {{ uploadStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" :disabled="row.status === 'uploading'" @click="removeFile(row.uid)">
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <ul class="file-upload-dialog__queue-list" aria-label="待上传文件列表">
          <li v-for="item in selectedFiles" :key="item.uid" class="file-upload-dialog__queue-item">
            <div class="file-upload-dialog__queue-file">
              <strong>{{ item.file.name }}</strong>
              <small v-if="item.relativePath">{{ item.relativePath }}</small>
              <small>{{ formatFileSize(item.file.size) }}</small>
            </div>
            <div class="file-upload-dialog__queue-actions">
              <el-tag :type="uploadStatusType(item.status)">{{ uploadStatusText(item.status) }}</el-tag>
              <el-button link type="danger" :disabled="item.status === 'uploading'" @click="removeFile(item.uid)">
                移除
              </el-button>
            </div>
          </li>
        </ul>
      </template>
      <el-empty v-else description="上传队列为空" />
    </div>

    <template #footer>
      <el-button :disabled="uploading" @click="visible = false">关闭</el-button>
      <el-button type="primary" :loading="uploading" :disabled="!selectedFiles.length" @click="uploadAll">开始上传</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
:global(.file-upload-dialog) {
  max-width: calc(100vw - 24px);
}

:global(.file-upload-dialog .el-dialog__body) {
  max-height: calc(100vh - 180px);
  overflow: auto;
}

.file-upload-dialog__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  color: var(--pfmt-text-muted);
}

.file-upload-dialog__conflict {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  margin-bottom: 14px;
  color: var(--pfmt-text-muted);
}

.file-upload-dialog__input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}

.file-upload-dialog__dropzone {
  position: relative;
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

.file-upload-dialog__picker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 32px;
  padding: 8px 15px;
  color: var(--pfmt-text);
  background: #ffffff;
  border: 1px solid var(--pfmt-border);
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  transition:
    border-color 0.2s ease,
    color 0.2s ease,
    background 0.2s ease;
}

.file-upload-dialog__picker:hover,
.file-upload-dialog__picker:focus-visible {
  color: var(--pfmt-primary);
  border-color: var(--pfmt-primary);
  outline: 0;
}

.file-upload-dialog__picker--primary {
  color: #ffffff;
  background: var(--pfmt-primary);
  border-color: var(--pfmt-primary);
}

.file-upload-dialog__picker--primary:hover,
.file-upload-dialog__picker--primary:focus-visible {
  color: #ffffff;
  background: #1d5fd1;
  border-color: #1d5fd1;
}

.file-upload-dialog__picker .el-icon {
  color: currentColor;
  font-size: 16px;
}

.file-upload-dialog__queue {
  margin-top: 14px;
}

.file-upload-dialog__queue-list {
  display: none;
  gap: 8px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.file-upload-dialog__queue-item {
  display: grid;
  gap: 8px;
  padding: 10px;
  background: #ffffff;
  border: 1px solid var(--pfmt-border-soft);
  border-radius: 8px;
}

.file-upload-dialog__queue-file {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.file-upload-dialog__queue-file strong,
.file-upload-dialog__queue-file small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-upload-dialog__queue-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.file-upload-dialog__queue small {
  display: block;
  margin-top: 4px;
  color: var(--pfmt-text-muted);
}

@media (max-width: 640px) {
  :global(.file-upload-dialog) {
    margin: 12px auto;
  }

  :global(.file-upload-dialog .el-dialog__body) {
    max-height: calc(100vh - 150px);
  }

  :global(.file-upload-dialog .el-dialog__footer) {
    display: flex;
    gap: 8px;
  }

  :global(.file-upload-dialog .el-dialog__footer .el-button) {
    flex: 1;
    margin-left: 0;
  }

  .file-upload-dialog__meta {
    align-items: flex-start;
    flex-direction: column;
  }

  .file-upload-dialog__conflict {
    align-items: flex-start;
    flex-direction: column;
  }

  .file-upload-dialog__dropzone {
    padding: 20px 12px;
  }

  .file-upload-dialog__dropzone h2 {
    font-size: 16px;
  }

  .file-upload-dialog__actions {
    display: grid;
    width: 100%;
    grid-template-columns: 1fr;
  }

  .file-upload-dialog__picker {
    width: 100%;
  }

  .file-upload-dialog__queue-table {
    display: none;
  }

  .file-upload-dialog__queue-list {
    display: grid;
  }
}
</style>
