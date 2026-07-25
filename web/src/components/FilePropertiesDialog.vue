<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { filesApi, tagsApi } from '@/api/files'
import type { FileDetail, FileInfo, FileTag, FileType } from '@/types/files'
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
const tagOptions = ref<FileTag[]>([])
const nameDraft = ref('')
const remarkDraft = ref('')
const summaryDraft = ref('')
const hiddenDraft = ref(false)
const tagDraft = ref<string[]>([])

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

function syncDraft(file: FileDetail | FileInfo | null) {
  nameDraft.value = file?.original_name ?? ''
  remarkDraft.value = file?.remark ?? ''
  summaryDraft.value = file?.summary_content ?? ''
  hiddenDraft.value = Boolean(file?.is_hidden)
  tagDraft.value = (file?.tags ?? []).map((tag) => tag.tag_name)
}

async function loadDetail() {
  const fileId = props.fileId ?? props.file?.file_id
  if (!fileId) {
    detail.value = null
    syncDraft(null)
    return
  }

  loading.value = true
  try {
    const [response, tags] = await Promise.all([filesApi.getFileDetail(fileId, props.showHidden), tagsApi.listTags()])
    detail.value = response
    tagOptions.value = tags
    syncDraft(response)
  } finally {
    loading.value = false
  }
}

async function saveMetadata() {
  const file = displayFile.value
  if (!file) {
    return
  }

  saving.value = true
  try {
    const normalizedName = nameDraft.value.trim()
    const normalizedRemark = remarkDraft.value.trim() ? remarkDraft.value : null
    const normalizedSummary = summaryDraft.value.trim() ? summaryDraft.value : null
    const saveShowHidden = props.showHidden || hiddenDraft.value
    let updated = await filesApi.updateFile(
      file.file_id,
      {
        original_name: normalizedName,
        remark: normalizedRemark,
        summary_content: normalizedSummary,
        is_hidden: hiddenDraft.value
      },
      saveShowHidden
    )
    updated = await filesApi.updateFileTags(file.file_id, tagDraft.value, saveShowHidden)
    detail.value = updated
    syncDraft(updated)
    emit('saved', updated)
    ElMessage.success('文件属性已保存')
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
        <el-form-item label="文件名">
          <el-input v-model="nameDraft" maxlength="512" show-word-limit />
        </el-form-item>
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
        <el-form-item label="摘要">
          <el-input
            v-model="summaryDraft"
            type="textarea"
            :rows="5"
            maxlength="8000"
            show-word-limit
            placeholder="添加人工摘要"
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="tagDraft"
            multiple
            filterable
            allow-create
            default-first-option
            class="file-properties-dialog__tags"
            placeholder="选择或输入标签"
          >
            <el-option
              v-for="tag in tagOptions"
              :key="tag.tag_id"
              :label="tag.tag_name"
              :value="tag.tag_name"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="showHidden || !displayFile.is_hidden" label="隐藏文件">
          <el-switch v-model="hiddenDraft" />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" :loading="saving" :disabled="!displayFile" @click="saveMetadata">保存属性</el-button>
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

.file-properties-dialog__tags {
  width: 100%;
}
</style>
