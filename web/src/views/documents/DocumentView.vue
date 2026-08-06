<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { TableKit } from '@tiptap/extension-table'
import type { EditorView } from '@tiptap/pm/view'
import type { Slice } from '@tiptap/pm/model'
import { TextSelection } from '@tiptap/pm/state'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Download,
  Grid,
  Link,
  List,
  MagicStick,
  Minus,
  Paperclip,
  Picture,
  Plus,
  Refresh,
  RefreshLeft,
  RefreshRight,
  Remove,
  Switch,
  UploadFilled
} from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { filesApi } from '@/api/files'
import DocumentEmbedDialog from '@/components/DocumentEmbedDialog.vue'
import DocumentOutline from '@/components/DocumentOutline.vue'
import { useSettingsStore } from '@/stores/settingsStore'
import type { DocumentContent, DocumentFormat } from '@/types/files'
import { ensureAttachmentFolder } from '@/utils/documentAttachments'
import { serializeMarkdownDocument, type ProseMirrorNode } from '@/utils/documentMarkdown'
import {
  addOutlineIdsToHtml,
  applyOutlineIdsToContainer,
  buildHtmlOutline,
  buildHtmlSourceOutline,
  buildMarkdownOutline
} from '@/utils/documentOutline'
import { saveBlobResponse } from '@/utils/download'
import { getEmbedToken, resolveEmbedUrls, stripEmbedTokens } from '@/utils/embedFiles'
import { renderMarkdown } from '@/utils/markdown'
import { beautifyText } from '@/utils/textBeautify'

type DocumentMode = 'read' | 'edit' | 'source'

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
const toolbarVersion = ref(0)
const activeOutlineId = ref('')
const canvasRef = ref<HTMLElement | null>(null)
const sourceRef = ref<HTMLTextAreaElement | null>(null)
const safeRenderedHtml = ref('')
const embedDialogVisible = ref(false)
const embedDialogMode = ref<'image' | 'file'>('image')
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
const showToolbar = computed(() => mode.value === 'edit' && documentContent.value?.document_format !== 'plain_text')
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

const toolbarActive = computed(() => {
  toolbarVersion.value
  const editorInstance = editor.value
  if (!editorInstance) {
    return {
      bold: false,
      italic: false,
      strike: false,
      code: false,
      bulletList: false,
      orderedList: false,
      blockquote: false,
      codeBlock: false,
      link: false,
      table: false
    }
  }
  return {
    bold: editorInstance.isActive('bold'),
    italic: editorInstance.isActive('italic'),
    strike: editorInstance.isActive('strike'),
    code: editorInstance.isActive('code'),
    bulletList: editorInstance.isActive('bulletList'),
    orderedList: editorInstance.isActive('orderedList'),
    blockquote: editorInstance.isActive('blockquote'),
    codeBlock: editorInstance.isActive('codeBlock'),
    link: editorInstance.isActive('link'),
    table: editorInstance.isActive('table')
  }
})

const headingLevel = computed({
  get: () => {
    toolbarVersion.value
    if (!editor.value?.isActive('heading')) {
      return 0
    }
    const attrs = editor.value.getAttributes('heading') as { level?: number }
    return Number(attrs.level ?? 1)
  },
  set: (level: number) => {
    if (level === 0) {
      editor.value?.chain().focus().setParagraph().run()
    } else {
      editor.value?.chain().focus().toggleHeading({ level: level as 1 | 2 | 3 | 4 | 5 | 6 }).run()
    }
  }
})

const editor = useEditor({
  extensions: [StarterKit, Image, TableKit],
  editable: true,
  content: '',
  editorProps: {
    handlePaste: handlePasteImages,
    handleDrop: handleDropImages
  },
  onCreate() {
    toolbarVersion.value += 1
  },
  onUpdate() {
    editorVersion.value += 1
    toolbarVersion.value += 1
    void nextTick(applyEditorOutlineIds)
  },
  onSelectionUpdate() {
    toolbarVersion.value += 1
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
    void setEditorContentFromSource()
  }
  if (nextMode === 'read') {
    void refreshRenderedHtml()
  }
  if (nextMode === 'source') {
    void nextTick(resizeSourceTextarea)
  }
  activeOutlineId.value = outlineItems.value[0]?.id ?? ''
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

async function setEditorContentFromSource() {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    return
  }
  let html = ''
  if (currentDocument.document_format === 'markdown') {
    html = renderMarkdown(sourceContent.value)
  } else if (currentDocument.document_format === 'html') {
    html = sourceContent.value
  } else {
    html = sourceContent.value
      .split(/\r?\n/)
      .map((line) => `<p>${escapeHtml(line) || '<br>'}</p>`)
      .join('')
  }
  const resolved = await resolveEmbedUrls(html)
  editor.value?.commands.setContent(resolved)
  editorVersion.value += 1
  await nextTick()
  applyEditorOutlineIds()
  resizeSourceTextarea()
}

async function refreshRenderedHtml() {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    safeRenderedHtml.value = ''
    return
  }
  if (currentDocument.document_format === 'markdown') {
    const rendered = renderMarkdown(currentDocument.content)
    safeRenderedHtml.value = addOutlineIdsToHtml(await resolveEmbedUrls(rendered))
    return
  }
  if (currentDocument.document_format === 'html') {
    const rendered = DOMPurify.sanitize(currentDocument.rendered_html ?? currentDocument.content)
    safeRenderedHtml.value = addOutlineIdsToHtml(await resolveEmbedUrls(rendered))
    return
  }
  safeRenderedHtml.value = addOutlineIdsToHtml(DOMPurify.sanitize(currentDocument.rendered_html ?? ''))
}

async function loadDocument() {
  if (!fileId.value) {
    documentContent.value = null
    sourceContent.value = ''
    safeRenderedHtml.value = ''
    return
  }

  loading.value = true
  try {
    const response = await filesApi.getDocument(fileId.value, settingsStore.showHiddenContent)
    documentContent.value = response
    sourceContent.value = response.content
    activeOutlineId.value = ''
    await setEditorContentFromSource()
    await refreshRenderedHtml()
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
  let content = ''
  if (mode.value === 'source') {
    content = sourceContent.value
  } else if (mode.value === 'edit') {
    if (currentDocument.document_format === 'html') {
      content = editor.value?.getHTML() ?? sourceContent.value
    } else if (currentDocument.document_format === 'markdown') {
      content = serializeMarkdownDocument(editor.value?.getJSON() as ProseMirrorNode | undefined) || sourceContent.value
    } else {
      content = editor.value?.getText() ?? sourceContent.value
    }
  } else {
    content = sourceContent.value
  }
  return stripEmbedTokens(content)
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
    await setEditorContentFromSource()
    await refreshRenderedHtml()
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

async function beautifyDocument() {
  const currentDocument = documentContent.value
  if (!currentDocument || mode.value === 'read') {
    return
  }

  const original = currentSaveContent()
  const formatted = beautifyText(original, currentDocument.document_format)
  if (formatted === original) {
    ElMessage.info('文本已符合规范，无需整理')
    return
  }

  const ruleDescriptions: Record<DocumentFormat, string> = {
    plain_text: '统一换行符、去除首尾空白、清理行尾空格、把单个换行补成空行、折叠多余空行',
    markdown: '统一换行符、去除首尾空白、折叠多余空行（代码块内部保持不变）',
    html: '统一换行符、去除首尾空白'
  }
  try {
    await ElMessageBox.confirm(
      `将整理当前文本：${ruleDescriptions[currentDocument.document_format]}。`,
      '整理文本',
      {
        type: 'warning',
        confirmButtonText: '应用',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }

  sourceContent.value = formatted
  if (mode.value === 'edit') {
    await setEditorContentFromSource()
  } else {
    await nextTick()
    resizeSourceTextarea()
  }
  ElMessage.success('整理完成')
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

function toggleMark(mark: 'bold' | 'italic' | 'strike' | 'code') {
  const commands = editor.value?.chain().focus()
  if (!commands) {
    return
  }
  if (mark === 'bold') {
    commands.toggleBold()
  } else if (mark === 'italic') {
    commands.toggleItalic()
  } else if (mark === 'strike') {
    commands.toggleStrike()
  } else {
    commands.toggleCode()
  }
  commands.run()
}

function toggleList(type: 'bulletList' | 'orderedList') {
  const editorInstance = editor.value
  if (!editorInstance) {
    return
  }
  if (type === 'bulletList') {
    editorInstance.chain().focus().toggleBulletList().run()
  } else {
    editorInstance.chain().focus().toggleOrderedList().run()
  }
}

async function toggleLink() {
  const editorInstance = editor.value
  if (!editorInstance) {
    return
  }
  const previousUrl = editorInstance.getAttributes('link').href as string | undefined
  if (previousUrl) {
    editorInstance.chain().focus().extendMarkRange('link').unsetLink().run()
    return
  }
  try {
    const { value } = await ElMessageBox.prompt('请输入链接地址', '插入链接', {
      inputValue: 'https://',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    editorInstance.chain().focus().extendMarkRange('link').setLink({ href: value }).run()
  } catch {
    // 用户取消
  }
}

function insertTable() {
  editor.value?.chain().focus().insertTable({ rows: 2, cols: 2, withHeaderRow: true }).run()
}

function openImageDialog() {
  embedDialogMode.value = 'image'
  embedDialogVisible.value = true
}

function openFileDialog() {
  embedDialogMode.value = 'file'
  embedDialogVisible.value = true
}

function handleEmbedInsert(payload: { fileId: string; originalName: string; fileType: string }) {
  void insertEmbed(payload.fileId, payload.originalName, payload.fileType)
}

async function insertEmbed(fileId: string, originalName: string, fileType: string) {
  const currentDocument = documentContent.value
  if (!currentDocument) {
    return
  }
  const tokenUrl = await getEmbedToken(fileId)
  const streamUrl = tokenUrl ?? `/api/files/${fileId}/stream`
  const editorInstance = editor.value
  if (!editorInstance) {
    return
  }
  if (fileType === 'image') {
    editorInstance.chain().focus().setImage({ src: streamUrl, alt: originalName }).run()
  } else {
    editorInstance.chain().focus().insertContent(`<a href="${streamUrl}">${escapeHtml(originalName)}</a>`).run()
  }
  editorVersion.value += 1
  void nextTick(applyEditorOutlineIds)
}

function imageFilesFrom(data: DataTransfer | null): File[] {
  if (!data) {
    return []
  }
  const files: File[] = []
  if (data.files) {
    files.push(...Array.from(data.files).filter((file) => file.type.startsWith('image/')))
  }
  if (data.items) {
    for (const item of Array.from(data.items)) {
      if (item.kind === 'file') {
        const file = item.getAsFile()
        if (file && file.type.startsWith('image/')) {
          files.push(file)
        }
      }
    }
  }
  return files
}

function handlePasteImages(_view: EditorView, event: ClipboardEvent, _slice: Slice): boolean {
  const files = imageFilesFrom(event.clipboardData)
  if (files.length === 0) {
    return false
  }
  void insertUploadedImages(files)
  return true
}

function handleDropImages(view: EditorView, event: DragEvent, _slice: Slice, moved: boolean): boolean {
  if (moved) {
    return false
  }
  const files = imageFilesFrom(event.dataTransfer)
  if (files.length === 0) {
    return false
  }
  event.preventDefault()
  const coordinates = view.posAtCoords({ left: event.clientX, top: event.clientY })
  if (coordinates) {
    view.dispatch(view.state.tr.setSelection(new TextSelection(view.state.doc.resolve(coordinates.pos))))
    view.focus()
  }
  void insertUploadedImages(files)
  return true
}

async function insertUploadedImages(files: File[]) {
  const currentDocument = documentContent.value
  if (!currentDocument || currentDocument.document_format === 'plain_text') {
    return
  }
  try {
    const attachmentPathId = await ensureAttachmentFolder(fromPathId.value ?? 'root', settingsStore.showHiddenContent)
    for (const file of files) {
      const uploaded = await filesApi.uploadFile({
        file,
        pathId: attachmentPathId,
        encryptionEnabled: true,
        conflictStrategy: 'rename'
      })
      insertEmbed(uploaded.file_id, uploaded.original_name, uploaded.file_type)
    }
    ElMessage.success(`已插入 ${files.length} 张图片`)
  } catch (error) {
    const message = error instanceof Error ? error.message : '图片上传失败'
    ElMessage.error(message)
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
        <el-button :icon="MagicStick" :disabled="!documentContent || mode === 'read'" @click="beautifyDocument">整理文本</el-button>
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
        <div v-if="showToolbar" class="document-view__toolbar">
          <el-select v-model="headingLevel" size="small" class="document-view__toolbar-heading" placeholder="标题">
            <el-option label="正文" :value="0" />
            <el-option v-for="level in [1, 2, 3, 4]" :key="level" :label="`标题 ${level}`" :value="level" />
          </el-select>

          <span class="document-view__toolbar-sep" />

          <el-button-group>
            <el-button
              size="small"
              :type="toolbarActive.bold ? 'primary' : 'default'"
              title="加粗"
              @click="toggleMark('bold')"
            >
              <b>B</b>
            </el-button>
            <el-button
              size="small"
              :type="toolbarActive.italic ? 'primary' : 'default'"
              title="斜体"
              @click="toggleMark('italic')"
            >
              <i>I</i>
            </el-button>
            <el-button
              size="small"
              :type="toolbarActive.strike ? 'primary' : 'default'"
              title="删除线"
              @click="toggleMark('strike')"
            >
              <s>S</s>
            </el-button>
            <el-button
              size="small"
              :type="toolbarActive.code ? 'primary' : 'default'"
              title="行内代码"
              @click="toggleMark('code')"
            >
              <code>&lt;/&gt;</code>
            </el-button>
          </el-button-group>

          <span class="document-view__toolbar-sep" />

          <el-button-group>
            <el-button
              size="small"
              :type="toolbarActive.bulletList ? 'primary' : 'default'"
              title="无序列表"
              :icon="List"
              @click="toggleList('bulletList')"
            />
            <el-button
              size="small"
              :type="toolbarActive.orderedList ? 'primary' : 'default'"
              title="有序列表"
              @click="toggleList('orderedList')"
            >
              1.
            </el-button>
          </el-button-group>

          <span class="document-view__toolbar-sep" />

          <el-button-group>
            <el-button
              size="small"
              :type="toolbarActive.blockquote ? 'primary' : 'default'"
              title="引用"
              @click="editor?.chain().focus().toggleBlockquote().run()"
            >
              ❝
            </el-button>
            <el-button
              size="small"
              :type="toolbarActive.codeBlock ? 'primary' : 'default'"
              title="代码块"
              @click="editor?.chain().focus().toggleCodeBlock().run()"
            >
              &lt;/&gt;
            </el-button>
            <el-button
              size="small"
              :type="toolbarActive.link ? 'primary' : 'default'"
              title="链接"
              :icon="Link"
              @click="toggleLink"
            />
            <el-button size="small" title="分割线" @click="editor?.chain().focus().setHorizontalRule().run()">—</el-button>
          </el-button-group>

          <span class="document-view__toolbar-sep" />

          <el-button-group>
            <el-button size="small" title="插入表格" :icon="Grid" @click="insertTable" />
            <template v-if="toolbarActive.table">
              <el-button size="small" title="上方插入行" :icon="Plus" @click="editor?.chain().focus().addRowBefore().run()" />
              <el-button size="small" title="下方插入行" :icon="Plus" @click="editor?.chain().focus().addRowAfter().run()" />
              <el-button size="small" title="左侧插入列" :icon="Plus" @click="editor?.chain().focus().addColumnBefore().run()" />
              <el-button size="small" title="右侧插入列" :icon="Plus" @click="editor?.chain().focus().addColumnAfter().run()" />
              <el-button size="small" title="删除当前行" :icon="Minus" @click="editor?.chain().focus().deleteRow().run()" />
              <el-button size="small" title="删除当前列" :icon="Minus" @click="editor?.chain().focus().deleteColumn().run()" />
              <el-button size="small" title="删除表格" :icon="Remove" @click="editor?.chain().focus().deleteTable().run()" />
            </template>
          </el-button-group>

          <span class="document-view__toolbar-sep" />

          <el-button-group>
            <el-button size="small" title="插入图片" :icon="Picture" @click="openImageDialog" />
            <el-button size="small" title="插入附件" :icon="Paperclip" @click="openFileDialog" />
          </el-button-group>

          <span class="document-view__toolbar-sep" />

          <el-button-group>
            <el-button size="small" title="撤销" :icon="RefreshLeft" @click="editor?.chain().focus().undo().run()" />
            <el-button size="small" title="重做" :icon="RefreshRight" @click="editor?.chain().focus().redo().run()" />
          </el-button-group>
        </div>

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

    <DocumentEmbedDialog
      v-model="embedDialogVisible"
      :mode="embedDialogMode"
      :parent-path-id="fromPathId ?? 'root'"
      @insert="handleEmbedInsert"
    />
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

.document-view__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  margin-bottom: 12px;
  background: #fff;
  border: 1px solid var(--pfmt-border);
  border-radius: 8px;
}

.document-view__toolbar-heading {
  width: 104px;
}

.document-view__toolbar-sep {
  width: 1px;
  height: 20px;
  background: var(--pfmt-border);
  margin: 0 2px;
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

.document-view__editor :deep(img) {
  max-width: 100%;
}

.document-view__editor :deep(table) {
  width: 100%;
  border-collapse: collapse;
}

.document-view__editor :deep(th),
.document-view__editor :deep(td) {
  border: 1px solid var(--pfmt-border);
  padding: 6px 10px;
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
