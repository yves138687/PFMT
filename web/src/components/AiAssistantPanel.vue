<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatLineRound, EditPen, DocumentChecked, MagicStick, Refresh, Upload } from '@element-plus/icons-vue'

import { aiApi } from '@/api/ai'
import { useSettingsStore } from '@/stores/settingsStore'
import type { AiReadScope, AiTask, AiTaskType } from '@/types/ai'
import type { DocumentContent } from '@/types/files'

const props = defineProps<{
  document: DocumentContent | null
  selectedText: string
  hidden: boolean
}>()

const emit = defineEmits<{
  summaryWritten: [summary: string]
}>()

const settingsStore = useSettingsStore()
const loading = ref(false)
const historyLoading = ref(false)
const writingSummaryTaskId = ref('')
const question = ref('')
const tasks = ref<AiTask[]>([])

const activeProvider = computed(() => settingsStore.activeAiProvider)
const configured = computed(
  () => settingsStore.settings.aiFeatureEnabled && Boolean(activeProvider.value?.id)
)
const selectedTextLength = computed(() => props.selectedText.trim().length)
const canUseSelection = computed(() => selectedTextLength.value > 0)
const latestTask = computed(() => tasks.value[0] ?? null)
const scopeText = computed(() => {
  if (!props.document) {
    return '未打开文档'
  }
  const parts = [`当前文档：${props.document.original_name}`]
  if (props.hidden) {
    parts.push('本次将读取隐藏内容')
  }
  parts.push(canUseSelection.value ? `选中文本：${selectedTextLength.value} 字` : '选中文本：无')
  return parts.join(' · ')
})

function parseScope(task: AiTask): AiReadScope {
  try {
    return JSON.parse(task.read_scope) as AiReadScope
  } catch {
    return {}
  }
}

async function loadHistory() {
  if (!props.document?.file_id) {
    tasks.value = []
    return
  }
  historyLoading.value = true
  try {
    const response = await aiApi.listTasks(props.document.file_id)
    tasks.value = response.items
  } finally {
    historyLoading.value = false
  }
}

async function runTask(taskType: AiTaskType) {
  if (!props.document) {
    return
  }
  if (!configured.value) {
    ElMessage.warning('请先在系统配置中启用 AI 并选择默认模型')
    return
  }
  if ((taskType === 'polish' || taskType === 'translate' || taskType === 'continue') && !canUseSelection.value) {
    ElMessage.warning('请先选择要处理的文本')
    return
  }
  const prompt = question.value.trim()
  if (taskType === 'qa' && !prompt) {
    ElMessage.warning('请输入问题')
    return
  }

  loading.value = true
  try {
    const task = await aiApi.createTask({
      file_id: props.document.file_id,
      task_type: taskType,
      prompt: prompt || null,
      selected_text: canUseSelection.value ? props.selectedText.trim() : null,
      provider_id: activeProvider.value?.id ?? null
    })
    tasks.value = [task, ...tasks.value.filter((item) => item.task_id !== task.task_id)]
    if (taskType === 'qa') {
      question.value = ''
    }
  } finally {
    loading.value = false
  }
}

async function writeSummary(task: AiTask) {
  if (task.task_type !== 'summary' || task.task_status !== 'success') {
    return
  }
  writingSummaryTaskId.value = task.task_id
  try {
    const file = await aiApi.writeSummary(task.task_id)
    emit('summaryWritten', file.summary_content ?? '')
    ElMessage.success('AI 摘要已写入文件属性')
  } finally {
    writingSummaryTaskId.value = ''
  }
}

watch(
  () => props.document?.file_id,
  () => {
    void loadHistory()
  },
  { immediate: true }
)
</script>

<template>
  <aside class="ai-assistant-panel">
    <div class="ai-assistant-panel__header">
      <div>
        <strong>AI 助手</strong>
        <p>{{ activeProvider?.model_name || '未选择模型' }}</p>
      </div>
      <el-button :icon="Refresh" circle :loading="historyLoading" title="刷新记录" @click="loadHistory" />
    </div>

    <el-alert
      v-if="!settingsStore.settings.aiFeatureEnabled"
      type="info"
      :closable="false"
      title="AI 功能未启用"
    />
    <el-alert
      v-else-if="!activeProvider"
      type="warning"
      :closable="false"
      title="请在系统配置中选择默认 AI 模型"
    />

    <div class="ai-assistant-panel__scope">
      {{ scopeText }}
    </div>

    <div class="ai-assistant-panel__actions">
      <el-button :icon="DocumentChecked" :loading="loading" :disabled="!document" @click="runTask('summary')">
        总结
      </el-button>
      <el-button :icon="EditPen" :loading="loading" :disabled="!document || !canUseSelection" @click="runTask('polish')">
        润色
      </el-button>
      <el-button :icon="ChatLineRound" :loading="loading" :disabled="!document || !canUseSelection" @click="runTask('translate')">
        翻译
      </el-button>
      <el-button :icon="MagicStick" :loading="loading" :disabled="!document || !canUseSelection" @click="runTask('continue')">
        扩写
      </el-button>
    </div>

    <div class="ai-assistant-panel__qa">
      <el-input
        v-model="question"
        type="textarea"
        :rows="3"
        maxlength="4000"
        show-word-limit
        placeholder="基于当前文档提问"
      />
      <el-button type="primary" :loading="loading" :disabled="!document" @click="runTask('qa')">
        提问
      </el-button>
    </div>

    <div v-if="latestTask" class="ai-assistant-panel__latest">
      <div class="ai-assistant-panel__task-heading">
        <span>{{ latestTask.task_type }}</span>
        <el-tag size="small" :type="latestTask.task_status === 'success' ? 'success' : 'info'">
          {{ latestTask.task_status }}
        </el-tag>
      </div>
      <p v-if="parseScope(latestTask).context_truncated" class="ai-assistant-panel__warning">
        上下文已截断
      </p>
      <pre>{{ latestTask.answer || latestTask.error_message || '暂无结果' }}</pre>
      <el-button
        v-if="latestTask.task_type === 'summary' && latestTask.task_status === 'success'"
        type="primary"
        plain
        :icon="Upload"
        :loading="writingSummaryTaskId === latestTask.task_id"
        @click="writeSummary(latestTask)"
      >
        写入摘要
      </el-button>
    </div>

    <el-empty v-else description="暂无 AI 记录" :image-size="72" />
  </aside>
</template>

<style scoped>
.ai-assistant-panel {
  display: grid;
  gap: 12px;
  align-self: start;
  min-width: 0;
  padding: 14px;
  background: #fff;
  border: 1px solid var(--pfmt-border);
  border-radius: 8px;
}

.ai-assistant-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.ai-assistant-panel__header p {
  margin: 4px 0 0;
  color: var(--pfmt-text-muted);
  font-size: 12px;
}

.ai-assistant-panel__scope {
  padding: 9px 10px;
  color: var(--pfmt-text-secondary);
  background: #f7f9fc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}

.ai-assistant-panel__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.ai-assistant-panel__actions :deep(.el-button) {
  margin: 0;
}

.ai-assistant-panel__qa {
  display: grid;
  gap: 8px;
}

.ai-assistant-panel__latest {
  display: grid;
  gap: 8px;
}

.ai-assistant-panel__task-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--pfmt-text-secondary);
  font-size: 13px;
}

.ai-assistant-panel__warning {
  margin: 0;
  color: var(--el-color-warning);
  font-size: 12px;
}

.ai-assistant-panel pre {
  max-height: 300px;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--pfmt-text);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.65;
}
</style>
