<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Download, Refresh, Switch, UploadFilled } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { filesApi } from '@/api/files'
import DocumentOutline from '@/components/DocumentOutline.vue'
import { useSettingsStore } from '@/stores/settingsStore'
import type { DocumentContent, DocumentFormat } from '@/types/files'
import {
  addOutlineIdsToHtml,
  applyOutlineIdsToContainer,
  buildHtmlOutline,
  buildHtmlSourceOutline,
  buildMarkdownOutline
} from '@/utils/documentOutline'
import { saveBlobResponse } from '@/utils/download'
import { renderMarkdown } from '@/utils/markdown'

type DocumentMode = 'read' | 'edit' | 'source'
type ProseMirrorNode = {
  type?: string
  text?: string
  attrs?: Record<string, unknown>
  marks?: Array<{ type?: string; attrs?: Record<string, unknown> }>
  content?: ProseMirrorNode[]
}

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()
const documentContent = ref<DocumentContent | null>(null)
const sourceContent = ref('')
const mode = ref<DocumentMode>('read')
const loading = ref(false)
const saving = ref(false)
const converting = ref(false)
const exporting = ref(false)
const convertVisible = ref(false)
const editorVersion = ref(0)
const activeOutlineId = ref('')
const canvasRef = ref<HTMLElement | null>(null)
const sourceRef = ref<HTMLTextAreaElement | null>(null)
const headingSelector = 'h1, h2, h3, h4, h5, h6'
const convertForm = ref<{ target_format: DocumentFormat; target_name: string }>({
  target_format: 'html',
  target_name: ''
})

const fileId = computed(() => (typeof route.params.fileId === 'string' ? route.params.fileId : ''))
const fromPathId = computed(() => {
  const pathId = route.query.pathId
  return typeof pathId === 'string' ? pathId : undefined
})
const safeRenderedHtml = computed(() => addOutlineIdsToHtml(DOMPurify.sanitize(documentContent.value?.rendered_html || '')))
const documentFormatText = computed(() => {
  const format = documentContent.value?.document_format
  if (format === 'markdown') {
    return 'Markdown'
  }
  if (format === 'html') {
    return 'HTML'
  }
  return '纯文本'
})
const outlineItems = computed(() => {
  const currentDocument = documentContent.value
  if (!currentDocument || currentDocument.document_format === 'plain_text') {
    return []
  }
  if (mode.value === 'source') {
    if (currentDocument.document_format === 'markdown') {
      return buildMarkdownOutline(sourceContent.value)
    }
    return buildHtmlSourceOutline(sourceContent.value)
  }
  if (mode.value === 'edit') {
    editorVersion.value
    return buildHtmlOutline(editor.value?.getHTML() ?? '')
  }
  if (currentDocument.document_format === 'markdown') {
    return buildMarkdownOutline(sourceContent.value)
  }
  return buildHtmlOutline(safeRenderedHtml.value)
})
const showOutline = computed(() => documentContent.value?.document_format !== 'plain_text')

const editor = useEditor({
  extensions: [StarterKit],
  editable: true,
  content: '',
  onUpdate() {
    editorVersion.value += 1
    void nextTick(applyEditorOutlineIds)
  }
})

function backToFolder() {
  void router.push({
    name: 'folder',
    params: {
      pathId: fromPathId.value ?? 'root'
    }
  })
}

function setMode(nextMode: DocumentMode) {
  if (mode.value === 'edit' && nextMode === 'source') {
    sourceContent.value = currentSaveContent()
  }
  mode.value = nextMode
  if (nextMode === 'edit') {
    editor.value?.commands.setContent(editorHtmlFromSource())
    editorVersion.value += 1
    void nextTick(applyEditorOutlineIds)
  }
  if (nextMode === 'source') {
    void nextTick(resizeSourceTextarea)
  }
  activeOutlineId.value = outlineItems.value[0]?.id ?? ''
}

function editorHtmlFromSource() {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    return ''
  }
  if (currentDocument.document_format === 'markdown') {
    return renderMarkdown(sourceContent.value)
  }
  if (currentDocument.document_format === 'html') {
    return sourceContent.value
  }
  return sourceContent.value
    .split(/\r?\n/)
    .map((line) => `<p>${escapeHtml(line) || '<br>'}</p>`)
    .join('')
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function handleModeChange(value: string | number | boolean | undefined) {
  if (value === 'read' || value === 'edit' || value === 'source') {
    setMode(value)
  }
}

async function loadDocument() {
  if (!fileId.value) {
    documentContent.value = null
    sourceContent.value = ''
    return
  }

  loading.value = true
  try {
    const response = await filesApi.getDocument(fileId.value, settingsStore.showHiddenContent)
    documentContent.value = response
    sourceContent.value = response.content
    editor.value?.commands.setContent(editorHtmlFromSource())
    editorVersion.value += 1
    activeOutlineId.value = ''
    await nextTick()
    applyEditorOutlineIds()
    resizeSourceTextarea()
    activeOutlineId.value = outlineItems.value[0]?.id ?? ''
  } finally {
    loading.value = false
  }
}

function currentSaveContent() {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    return ''
  }
  if (mode.value === 'source') {
    return sourceContent.value
  }
  if (mode.value === 'edit') {
    if (currentDocument.document_format === 'html') {
      return editor.value?.getHTML() ?? sourceContent.value
    }
    if (currentDocument.document_format === 'markdown') {
      return serializeMarkdownDocument(editor.value?.getJSON() as ProseMirrorNode | undefined) || sourceContent.value
    }
    return editor.value?.getText() ?? sourceContent.value
  }
  return sourceContent.value
}

function serializeMarkdownDocument(node: ProseMirrorNode | undefined): string {
  if (!node?.content) {
    return ''
  }
  return node.content.map((child) => serializeMarkdownBlock(child, 0)).join('\n\n').trimEnd()
}

function serializeMarkdownBlock(node: ProseMirrorNode, depth: number): string {
  const children = node.content ?? []
  if (node.type === 'heading') {
    const level = Number(node.attrs?.level ?? 1)
    return `${'#'.repeat(Math.min(Math.max(level, 1), 6))} ${serializeInline(children)}`
  }
  if (node.type === 'paragraph') {
    return serializeInline(children)
  }
  if (node.type === 'bulletList') {
    return children.map((child) => serializeListItem(child, depth, '-')).join('\n')
  }
  if (node.type === 'orderedList') {
    return children.map((child, index) => serializeListItem(child, depth, `${index + 1}.`)).join('\n')
  }
  if (node.type === 'blockquote') {
    return children
      .map((child) => serializeMarkdownBlock(child, depth))
      .join('\n')
      .split('\n')
      .map((line) => `> ${line}`)
      .join('\n')
  }
  if (node.type === 'codeBlock') {
    return `\`\`\`\n${serializeInline(children)}\n\`\`\``
  }
  if (node.type === 'horizontalRule') {
    return '---'
  }
  return serializeInline(children)
}

function serializeListItem(node: ProseMirrorNode, depth: number, marker: string): string {
  const indent = '  '.repeat(depth)
  const blocks = node.content ?? []
  const [firstBlock, ...restBlocks] = blocks
  const firstLine = firstBlock ? serializeMarkdownBlock(firstBlock, depth + 1) : ''
  const rest = restBlocks.map((child) => serializeMarkdownBlock(child, depth + 1)).filter(Boolean)
  const first = `${indent}${marker} ${firstLine}`
  return [first, ...rest.map((line) => `${indent}  ${line}`)].join('\n')
}

function serializeInline(nodes: ProseMirrorNode[]): string {
  return nodes.map((node) => {
    if (node.type === 'text') {
      return applyMarkdownMarks(node.text ?? '', node.marks ?? [])
    }
    if (node.type === 'hardBreak') {
      return '  \n'
    }
    return serializeInline(node.content ?? [])
  }).join('')
}

function applyMarkdownMarks(text: string, marks: NonNullable<ProseMirrorNode['marks']>): string {
  return marks.reduce((result, mark) => {
    if (mark.type === 'bold') {
      return `**${result}**`
    }
    if (mark.type === 'italic') {
      return `*${result}*`
    }
    if (mark.type === 'code') {
      return `\`${result}\``
    }
    if (mark.type === 'strike') {
      return `~~${result}~~`
    }
    if (mark.type === 'link' && typeof mark.attrs?.href === 'string') {
      return `[${result}](${mark.attrs.href})`
    }
    return result
  }, text)
}

async function saveDocument() {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    return
  }

  saving.value = true
  try {
    const response = await filesApi.saveDocument(
      currentDocument.file_id,
      {
        document_format: currentDocument.document_format,
        content: currentSaveContent()
      },
      settingsStore.showHiddenContent
    )
    documentContent.value = response
    sourceContent.value = response.content
    editor.value?.commands.setContent(editorHtmlFromSource())
    editorVersion.value += 1
    await nextTick()
    applyEditorOutlineIds()
    resizeSourceTextarea()
    activeOutlineId.value = outlineItems.value[0]?.id ?? ''
    ElMessage.success('文档已保存')
  } finally {
    saving.value = false
  }
}

async function exportDocument() {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    return
  }

  exporting.value = true
  try {
    const response = await filesApi.exportFile(currentDocument.file_id, settingsStore.showHiddenContent)
    saveBlobResponse(response, currentDocument.original_name)
    ElMessage.success('文件已开始导出')
  } finally {
    exporting.value = false
  }
}

function applyEditorOutlineIds() {
  if (mode.value !== 'edit') {
    return
  }
  applyOutlineIdsToContainer(canvasRef.value?.querySelector('.ProseMirror') ?? null)
}

function scrollToOutline(id: string, index = -1) {
  const container = canvasRef.value
  if (!container) {
    return
  }

  if (mode.value === 'source') {
    scrollSourceToOutline(id)
    return
  }

  const target = findOutlineTarget(container, id, index)
  if (!target) {
    return
  }

  activeOutlineId.value = id
  scrollElementIntoCanvas(container, target)
}

function updateActiveOutline() {
  const container = canvasRef.value
  if (!container || outlineItems.value.length === 0) {
    activeOutlineId.value = ''
    return
  }

  if (mode.value === 'source') {
    updateActiveSourceOutline(container)
    return
  }

  const headings = outlineItems.value
    .map((item, index) => {
      const element = findOutlineTarget(container, item.id, index)
      if (!element) {
        return null
      }
      const top = element.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop
      return { id: item.id, top }
    })
    .filter((item): item is { id: string; top: number } => item !== null)

  const current = headings
    .filter((heading) => heading.top <= container.scrollTop + 32)
    .at(-1)

  activeOutlineId.value = current?.id ?? headings[0]?.id ?? ''
}

function findOutlineTarget(container: HTMLElement, id: string, index = -1) {
  const headings = Array.from(container.querySelectorAll<HTMLElement>(headingSelector))
  if (index >= 0 && headings[index]) {
    return headings[index]
  }

  const selector = typeof CSS !== 'undefined' && CSS.escape ? `#${CSS.escape(id)}` : `[data-outline-id="${id}"]`
  return container.querySelector<HTMLElement>(selector)
}

function scrollElementIntoCanvas(container: HTMLElement, target: HTMLElement) {
  const targetTop = target.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop
  const canScrollCanvas = container.scrollHeight > container.clientHeight + 1

  if (canScrollCanvas) {
    container.scrollTo({
      top: targetTop - 14,
      behavior: 'smooth'
    })
    return
  }

  target.scrollIntoView({
    behavior: 'smooth',
    block: 'start'
  })
}

function scrollSourceToOutline(id: string) {
  const container = canvasRef.value
  const textarea = sourceRef.value
  const item = outlineItems.value.find((outlineItem) => outlineItem.id === id)
  if (!container || !textarea || item?.sourceLine === undefined) {
    return
  }

  const lineHeight = Number.parseFloat(getComputedStyle(textarea).lineHeight) || 24
  activeOutlineId.value = id
  container.scrollTo({
    top: item.sourceLine * lineHeight,
    behavior: 'smooth'
  })
  focusSourceLine(item.sourceLine)
}

function updateActiveSourceOutline(container: HTMLElement) {
  const textarea = sourceRef.value
  if (!textarea) {
    activeOutlineId.value = outlineItems.value[0]?.id ?? ''
    return
  }

  const lineHeight = Number.parseFloat(getComputedStyle(textarea).lineHeight) || 24
  const currentLine = Math.max(0, Math.floor((container.scrollTop + 20) / lineHeight))
  const current = outlineItems.value
    .filter((item) => item.sourceLine !== undefined && item.sourceLine <= currentLine)
    .at(-1)

  activeOutlineId.value = current?.id ?? outlineItems.value[0]?.id ?? ''
}

function focusSourceLine(line: number) {
  const textarea = sourceRef.value
  if (!textarea) {
    return
  }

  const lines = sourceContent.value.split(/\r?\n/)
  const start = lines.slice(0, line).reduce((offset, currentLine) => offset + currentLine.length + 1, 0)
  textarea.focus()
  textarea.setSelectionRange(start, start)
}

function resizeSourceTextarea() {
  const textarea = sourceRef.value
  if (!textarea) {
    return
  }

  textarea.style.height = 'auto'
  textarea.style.height = `${Math.max(textarea.scrollHeight, 420)}px`
}

function openConvertDialog() {
  const currentFormat = documentContent.value?.document_format
  convertForm.value = {
    target_format: currentFormat === 'html' ? 'markdown' : 'html',
    target_name: ''
  }
  convertVisible.value = true
}

async function convertDocument() {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    return
  }

  converting.value = true
  try {
    const converted = await filesApi.convertDocument(
      currentDocument.file_id,
      {
        target_format: convertForm.value.target_format,
        target_name: convertForm.value.target_name.trim() || null
      },
      settingsStore.showHiddenContent
    )
    convertVisible.value = false
    ElMessage.success('已生成转换后的新文件')
    void router.push({
      name: 'document',
      params: {
        fileId: converted.file_id
      },
      query: {
        pathId: converted.path_id
      }
    })
  } finally {
    converting.value = false
  }
}

watch(
  [fileId, () => settingsStore.showHiddenContent],
  () => {
    void loadDocument()
  },
  { immediate: true }
)

watch(outlineItems, (items) => {
  activeOutlineId.value = items[0]?.id ?? ''
  void nextTick(() => {
    applyEditorOutlineIds()
    updateActiveOutline()
  })
})

watch(sourceContent, () => {
  if (mode.value === 'source') {
    void nextTick(resizeSourceTextarea)
  }
})

onBeforeUnmount(() => {
  editor.value?.destroy()
})
</script>

<template>
  <section class="page-shell document-view">
    <div class="page-heading">
      <div>
        <h1>{{ documentContent?.original_name || '文档' }}</h1>
        <p>{{ documentFormatText }} · {{ documentContent?.size_bytes ?? 0 }} B</p>
      </div>
      <div class="document-view__actions">
        <el-button :icon="ArrowLeft" @click="backToFolder">返回列表</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadDocument">刷新</el-button>
        <el-button :icon="Download" :loading="exporting" :disabled="!documentContent" @click="exportDocument">导出</el-button>
        <el-button :icon="Switch" :disabled="!documentContent" @click="openConvertDialog">转换</el-button>
        <el-button type="primary" :icon="UploadFilled" :loading="saving" :disabled="!documentContent" @click="saveDocument">
          保存
        </el-button>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <el-radio-group :model-value="mode" size="small" @change="handleModeChange">
          <el-radio-button label="read">阅读</el-radio-button>
          <el-radio-button label="edit">编辑</el-radio-button>
          <el-radio-button label="source">源码</el-radio-button>
        </el-radio-group>
        <span class="muted">统一文档打开</span>
      </div>
      <div v-loading="loading" class="panel-body document-view__body">
        <div v-if="documentContent" class="document-view__workspace" :class="{ 'document-view__workspace--with-outline': showOutline }">
          <div
            ref="canvasRef"
            class="document-view__canvas"
            :class="`document-view__canvas--${mode}`"
            @scroll="updateActiveOutline"
          >
            <article v-if="mode === 'read'" class="document-view__rendered" v-html="safeRenderedHtml" />
            <EditorContent v-else-if="mode === 'edit'" class="document-view__editor" :editor="editor" />
            <textarea
              v-else
              ref="sourceRef"
              v-model="sourceContent"
              class="document-view__source"
              @input="resizeSourceTextarea"
            />
          </div>
          <DocumentOutline
            v-if="showOutline"
            :items="outlineItems"
            :active-id="activeOutlineId"
            @navigate="scrollToOutline"
          />
        </div>
        <el-empty v-else description="暂无文档内容" />
      </div>
    </section>

    <el-dialog v-model="convertVisible" title="转换为新文件" width="420px">
      <el-form label-position="top">
        <el-form-item label="目标格式">
          <el-select v-model="convertForm.target_format">
            <el-option label="纯文本" value="plain_text" />
            <el-option label="Markdown" value="markdown" />
            <el-option label="HTML" value="html" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标文件名">
          <el-input v-model="convertForm.target_name" placeholder="留空则使用原文件名" maxlength="512" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="convertVisible = false">取消</el-button>
        <el-button type="primary" :loading="converting" @click="convertDocument">生成新文件</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.document-view {
  display: grid;
  gap: 16px;
}

.document-view__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.document-view__body {
  display: flex;
  flex-direction: column;
  min-height: 68vh;
}

.document-view__workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
}

.document-view__workspace--with-outline {
  grid-template-columns: minmax(0, 1fr) 220px;
  align-items: start;
}

.document-view__canvas {
  flex: 1;
  min-height: 62vh;
  max-height: calc(100vh - 210px);
  overflow: auto;
  padding: 18px;
  background: #fff;
  border: 1px solid var(--pfmt-border);
  border-radius: 8px;
  color: var(--pfmt-text);
  line-height: 1.75;
}

.document-view__canvas--source {
  padding: 18px;
}

.document-view__rendered,
.document-view__editor,
.document-view__source {
  min-height: calc(62vh - 36px);
}

.document-view__rendered :deep(h1),
.document-view__rendered :deep(h2),
.document-view__rendered :deep(h3) {
  scroll-margin-top: 16px;
  margin: 1.2em 0 0.5em;
  line-height: 1.35;
}

.document-view__rendered :deep(h4),
.document-view__rendered :deep(h5),
.document-view__rendered :deep(h6),
.document-view__editor :deep(h1),
.document-view__editor :deep(h2),
.document-view__editor :deep(h3),
.document-view__editor :deep(h4),
.document-view__editor :deep(h5),
.document-view__editor :deep(h6) {
  scroll-margin-top: 16px;
}

.document-view__editor :deep(.ProseMirror) {
  min-height: calc(62vh - 36px);
  outline: none;
}

.document-view__source {
  width: 100%;
  min-height: calc(62vh - 36px);
  padding: 0;
  overflow: hidden;
  resize: none;
  border: 0;
  outline: none;
  color: var(--pfmt-text);
  background: transparent;
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace;
  font-size: 14px;
  line-height: 1.7;
}

.document-view__canvas:focus-within {
  border-color: var(--el-color-primary);
}

@media (max-width: 960px) {
  .document-view__workspace--with-outline {
    grid-template-columns: minmax(0, 1fr);
  }

  .document-view__canvas {
    max-height: none;
  }
}
</style>
