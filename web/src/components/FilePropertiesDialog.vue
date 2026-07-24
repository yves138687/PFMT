<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { filesApi } from '@/api/files'
import type { FileDetail, FileInfo, FileType } from '@/types/files'
import { formatDateTime, formatFileSize } from '@/utils/format'

const props = defineProps<{
  modelValue: boolean
  fileId?: string
  file?: FileDetail | FileInfo | null
  showHidden?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [file: FileDetail]
}>()

const loading = ref(false)
const saving = ref(false)
const detail = ref<FileDetail | null>(null)
const remarkDraft = ref('')

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const displayFile = computed(() => detail.value ?? props.file ?? null)

const fileTypeLabels: Record<FileType, string> = {
  text: '文本',
  image: '图片',
  video: '视频',
  pdf: 'PDF',
  audio: '音频',
  other: '其他'
}

function booleanText(value?: boolean) {
  return value ? '是' : '否'
}

function fileTypeText(value?: FileType) {
  return value ? fileTypeLabels[value] : '-'
}

async function loadDetail() {
  const fileId = props.fileId ?? props.file?.file_id
  if (!fileId) {
    detail.value = null
    remarkDraft.value = ''
    return
  }

  loading.value = true
  try {
    const response = await filesApi.getFileDetail(fileId, props.showHidden)
    detail.value = response
    remarkDraft.value = response.remark ?? ''
  } finally {
    loading.value = false
  }
}

async function saveRemark() {
  const file = displayFile.value
  if (!file) {
    return
  }

  saving.value = true
  try {
    const normalizedRemark = remarkDraft.value.trim() ? remarkDraft.value : null
    const updated = await filesApi.updateFileRemark(file.file_id, normalizedRemark, props.showHidden)
    detail.value = updated
    remarkDraft.value = updated.remark ?? ''
    emit('saved', updated)
    ElMessage.success('文件备注已保存')
  } finally {
    saving.value = false
  }
}

watch(
  () => [props.modelValue, props.fileId, props.file?.file_id, props.showHidden] as const,
  ([isOpen]) => {
    if (isOpen) {
      void loadDetail()
    }
  },
  { immediate: true }
)
</script>

<template>
  <el-dialog v-model="visible" title="属性" width="640px" class="file-properties-dialog">
    <div v-loading="loading" class="file-properties-dialog__body">
      <el-descriptions v-if="displayFile" :column="1" border>
        <el-descriptions-item label="文件名">{{ displayFile.original_name }}</el-descriptions-item>
        <el-descriptions-item label="文件路径">
          {{ 'logical_path' in displayFile ? displayFile.logical_path : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="文件大小">{{ formatFileSize(displayFile.size_bytes) }}</el-descriptions-item>
        <el-descriptions-item label="文件类型">{{ fileTypeText(displayFile.file_type) }}</el-descriptions-item>
        <el-descriptions-item label="MIME">{{ displayFile.mime_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="扩展名">{{ displayFile.file_ext || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(displayFile.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDateTime(displayFile.updated_at) }}</el-descriptions-item>
        <el-descriptions-item label="最近访问">{{ formatDateTime(displayFile.last_accessed_at) }}</el-descriptions-item>
        <el-descriptions-item label="加密">{{ booleanText(displayFile.encryption_enabled) }}</el-descriptions-item>
        <el-descriptions-item label="隐藏">{{ booleanText(displayFile.is_hidden) }}</el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="暂无文件属性" />

      <el-form v-if="displayFile" class="file-properties-dialog__remark" label-position="top">
        <el-form-item label="文件备注">
          <el-input
            v-model="remarkDraft"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="添加文件备注"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" :loading="saving" :disabled="!displayFile" @click="saveRemark">保存备注</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.file-properties-dialog__body {
  display: grid;
  gap: 16px;
}

.file-properties-dialog__remark {
  margin-top: 2px;
}
</style>
