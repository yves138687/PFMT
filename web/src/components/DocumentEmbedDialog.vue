<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Picture, UploadFilled } from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { ensureAttachmentFolder } from '@/utils/documentAttachments'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileInfo } from '@/types/files'

const props = defineProps<{
  modelValue: boolean
  mode: 'image' | 'file'
  parentPathId: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'insert', payload: { fileId: string; originalName: string; fileType: string }): void
}>()

const settingsStore = useSettingsStore()
const activeTab = ref<'upload' | 'pick'>('upload')
const uploading = ref(false)
const pickLoading = ref(false)
const pickQuery = ref('')
const pickFiles = ref<FileInfo[]>([])

const title = computed(() => (props.mode === 'image' ? '插入图片' : '插入附件'))
const accept = computed(() => (props.mode === 'image' ? 'image/png,image/jpeg,image/gif,image/webp' : undefined))
const canPick = computed(() => props.mode === 'image' ? pickFiles.value.filter((item) => item.file_type === 'image') : pickFiles.value)

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      activeTab.value = 'upload'
      pickQuery.value = ''
      void loadPickFiles()
    }
  }
)

async function handleFileChange(file: { raw?: File }) {
  const raw = file.raw
  if (!raw) {
    return
  }
  if (props.mode === 'image' && !raw.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  uploading.value = true
  try {
    const attachmentPathId = await ensureAttachmentFolder(props.parentPathId, settingsStore.showHiddenContent)
    const uploaded = await filesApi.uploadFile({
      file: raw,
      pathId: attachmentPathId,
      encryptionEnabled: true,
      conflictStrategy: 'rename'
    })
    emit('insert', { fileId: uploaded.file_id, originalName: uploaded.original_name, fileType: uploaded.file_type })
    close()
    ElMessage.success('已上传并插入')
  } catch (error) {
    const message = error instanceof Error ? error.message : '上传失败'
    ElMessage.error(message)
  } finally {
    uploading.value = false
  }
}

async function loadPickFiles() {
  pickLoading.value = true
  try {
    const items = await filesApi.listFiles(props.parentPathId, settingsStore.showHiddenContent)
    pickFiles.value = items
  } catch {
    pickFiles.value = []
  } finally {
    pickLoading.value = false
  }
}

async function searchPickFiles() {
  const query = pickQuery.value.trim()
  if (!query) {
    await loadPickFiles()
    return
  }
  pickLoading.value = true
  try {
    const response = await filesApi.searchFiles(query, settingsStore.showHiddenContent)
    pickFiles.value = response.items
  } catch {
    pickFiles.value = []
  } finally {
    pickLoading.value = false
  }
}

function pickInsert(file: FileInfo) {
  emit('insert', { fileId: file.file_id, originalName: file.original_name, fileType: file.file_type })
  close()
}

function close() {
  emit('update:modelValue', false)
}

function formatSize(size: number): string {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>

<template>
  <el-dialog :model-value="modelValue" :title="title" width="560px" @update:model-value="close">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="上传本地文件" name="upload">
        <el-upload
          drag
          :accept="accept"
          :auto-upload="false"
          :show-file-list="false"
          :disabled="uploading"
          :on-change="handleFileChange"
        >
          <el-icon class="document-embed-dialog__icon"><UploadFilled /></el-icon>
          <div class="el-upload__text">点击或拖拽{{ props.mode === 'image' ? '图片' : '文件' }}到此处</div>
          <template #tip>
            <div class="el-upload__tip">
              上传后自动保存到本目录的「附件」文件夹，并在文档中插入引用
            </div>
          </template>
        </el-upload>
      </el-tab-pane>
      <el-tab-pane label="从知识库选择" name="pick">
        <el-input
          v-model="pickQuery"
          placeholder="搜索文件名、备注、类型"
          clearable
          @keyup.enter="searchPickFiles"
          @clear="loadPickFiles"
        >
          <template #append>
            <el-button :loading="pickLoading" @click="searchPickFiles">搜索</el-button>
          </template>
        </el-input>
        <div v-loading="pickLoading" class="document-embed-dialog__pick-list">
          <el-empty v-if="canPick.length === 0" description="暂无可用文件" :image-size="72" />
          <div
            v-for="file in canPick"
            :key="file.file_id"
            class="document-embed-dialog__pick-item"
            @click="pickInsert(file)"
          >
            <el-icon><Picture v-if="file.file_type === 'image'" /><Document v-else /></el-icon>
            <div class="document-embed-dialog__pick-name" :title="file.original_name">{{ file.original_name }}</div>
            <div class="document-embed-dialog__pick-meta">{{ formatSize(file.size_bytes) }}</div>
            <el-button size="small" type="primary" plain>插入</el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="close">取消</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.document-embed-dialog__icon {
  font-size: 48px;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}

.document-embed-dialog__pick-list {
  max-height: 320px;
  margin-top: 12px;
  overflow: auto;
}

.document-embed-dialog__pick-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--pfmt-border);
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.document-embed-dialog__pick-item:hover {
  border-color: var(--el-color-primary);
}

.document-embed-dialog__pick-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-embed-dialog__pick-meta {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
