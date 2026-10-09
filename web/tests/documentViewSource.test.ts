import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(__dirname, '../src/views/documents/DocumentView.vue'), 'utf-8')

describe('DocumentView source contract', () => {
  it('keeps unified read edit and source modes on one document page', () => {
    expect(source).toContain("type DocumentMode = 'read' | 'edit' | 'source'")
    expect(source).toContain('阅读')
    expect(source).toContain('编辑')
    expect(source).toContain('源码')
    expect(source).toContain('document-view__canvas')
    expect(source).toContain('<textarea')
    expect(source).toContain('class="document-view__source"')
    expect(source).toContain('@tiptap/vue-3')
    expect(source).toContain('@tiptap/starter-kit')
    expect(source).toContain('EditorContent')
  })

  it('uses document APIs for loading saving and conversion', () => {
    expect(source).toContain('filesApi.getDocument')
    expect(source).toContain('filesApi.saveDocument')
    expect(source).toContain('filesApi.convertDocument')
    expect(source).toContain('filesApi.exportFile')
    expect(source).toContain('exportDocument')
    expect(source).toContain('导出')
    expect(source).toContain('saveBlobResponse')
    expect(source).toContain('生成新文件')
    expect(source).toContain("name: 'document'")
  })

  it('loads documents through a fast read path before preparing the rich editor', () => {
    expect(source).toContain('const LARGE_DOCUMENT_SIZE_BYTES = 512 * 1024')
    expect(source).toContain('const RICH_EDITOR_CONFIRM_SIZE_BYTES = 2 * 1024 * 1024')
    expect(source).toContain("const nextMode = documentContent.value?.file_id === requestedFileId ? mode.value : 'read'")
    expect(source).toContain('async function prepareEditorContent()')
    expect(source).toContain('const editorLoading = ref(false)')
    expect(source).toContain('await prepareEditorContent()')
    expect(source).toContain('element-loading-text="正在准备编辑器"')
    expect(source).toContain('currentDocument.rendered_html')
    expect(source).toContain('async function renderReadableHtml(html: string)')
    expect(source).toContain('observeRenderedEmbeds()')
    expect(source).not.toContain('await setEditorContentFromSource()\n    await refreshRenderedHtml()')
  })

  it('renders only one chapter or paragraph group at a time in read mode', () => {
    expect(source).toContain("import { buildReadSections } from '@/utils/documentReading'")
    expect(source).toContain('const readSections = computed')
    expect(source).toContain('const activeReadSection = computed')
    expect(source).toContain('async function selectReadSection')
    expect(source).toContain('one chapter/paragraph')
    expect(source).toContain('上一节')
    expect(source).toContain('下一节')
  })

  it('warns before preparing rich editing for very large documents', () => {
    expect(source).toContain('const isLargeDocument = computed')
    expect(source).toContain('const requiresRichEditorConfirm = computed')
    expect(source).toContain('const largeDocumentHint = computed')
    expect(source).toContain("v-if=\"largeDocumentHint\"")
    expect(source).toContain('大文档编辑')
    expect(source).toContain('继续编辑')
  })

  it('resolves read-mode embedded files lazily near the viewport', () => {
    expect(source).toContain('let renderedEmbedObserver: IntersectionObserver | null = null')
    expect(source).toContain('function observeRenderedEmbeds()')
    expect(source).toContain("rootMargin: '520px 0px'")
    expect(source).toContain('async function resolveRenderedEmbed')
    expect(source).toContain('getEmbedToken(fileId)')
    expect(source).toContain('disconnectRenderedEmbedObserver()')
  })

  it('serializes rich editor content back to markdown instead of plain text', () => {
    expect(source).toContain('serializeMarkdownDocument')
    expect(source).toContain('@/utils/documentMarkdown')
    expect(source).toContain("currentDocument.document_format === 'markdown'")
    expect(source).not.toContain("currentDocument.document_format === 'markdown') {\n      return editor.value?.getText()")
  })

  it('keeps source mode as a full-size code editing area', () => {
    expect(source).toContain('.document-view__canvas')
    expect(source).toContain("document-view__canvas--source")
    expect(source).toContain('.document-view__source')
    expect(source).toContain('min-height: 62vh')
    expect(source).toContain('font-family: ui-monospace')
    expect(source).toContain('overflow: auto')
    expect(source).toContain('resize: none')
    expect(source).toContain('@scroll="updateActiveOutline"')
  })

  it('supports rich text toolbar with images attachments and tables', () => {
    expect(source).toContain("@tiptap/extension-image")
    expect(source).toContain("TableKit")
    expect(source).toContain("DocumentEmbedDialog")
    expect(source).toContain("插入图片")
    expect(source).toContain("插入附件")
    expect(source).toContain("插入表格")
    expect(source).toContain("resolveEmbedUrls")
    expect(source).toContain("stripEmbedTokens")
    expect(source).toContain("serializeMarkdownDocument")
    expect(source).toContain("ensureAttachmentFolder")
  })

  it('opens document images in a reusable preview from read and edit modes', () => {
    expect(source).toContain("DocumentImagePreview")
    expect(source).toContain("extractDocumentImageFileId")
    expect(source).toContain("@dblclick=\"openDocumentImagePreview\"")
    expect(source).toContain("filesApi.getPreviewBlob")
    expect(source).toContain("URL.createObjectURL")
    expect(source).toContain("URL.revokeObjectURL")
    expect(source).toContain("cursor: zoom-in")
  })

  it('keeps the beautify/cleanup feature wired into the document page', () => {
    expect(source).toContain("import { beautifyText } from '@/utils/textBeautify'")
    expect(source).toContain('MagicStick')
    expect(source).toContain('beautifyDocument')
    expect(source).toContain('beautifyText(original, currentDocument.document_format)')
    expect(source).toContain('ElMessageBox.confirm')
    expect(source).toContain('整理文本')
    expect(source).toContain('v-if="mode !== \'read\'" :icon="MagicStick"')
  })

  it('provides temporary reading-only font-size controls', () => {
    expect(source).toContain('const DEFAULT_READ_FONT_SIZE = 15')
    expect(source).toContain('const MIN_READ_FONT_SIZE = 12')
    expect(source).toContain('const MAX_READ_FONT_SIZE = 24')
    expect(source).toContain('const readFontSize = ref(DEFAULT_READ_FONT_SIZE)')
    expect(source).toContain('function decreaseReadFontSize()')
    expect(source).toContain('function increaseReadFontSize()')
    expect(source).toContain('v-if="mode === \'read\'" class="document-view__reading-row"')
    expect(source).toContain('@click="decreaseReadFontSize"')
    expect(source).toContain('@click="increaseReadFontSize"')
    expect(source).toContain('{{ readFontSize }}px')
    expect(source).toContain(':style="{ \'--document-read-font-size\': `${readFontSize}px` }"')
    expect(source).toContain('font-size: var(--document-read-font-size);')
  })

  it('compacts editing tools and moves the outline into a mobile drawer', () => {
    expect(source).toContain('MoreFilled')
    expect(source).toContain('document-view__toolbar-more')
    expect(source).toContain('更多编辑工具')
    expect(source).toContain('outlineDrawerVisible')
    expect(source).toContain('文档目录')
    expect(source).toContain('navigateOutline')
    expect(source).toContain('document-view__desktop-outline')
    expect(source).toContain('document-view__mode-label')
    expect(source).toContain('@media (max-width: 820px)')
  })

  it('keeps AI and the rich editor out of the reading workspace', () => {
    expect(source).toContain("const showAiAssistant = computed(() => mode.value === 'edit' && aiPanelOpen.value)")
    expect(source).toContain('v-if="showAiAssistant" class="document-view__ai-workspace"')
    expect(source).toContain("if (previousMode === 'edit' && nextMode !== 'edit')")
    expect(source).toContain('editor.value?.commands.clearContent()')
    expect(source).toContain('编辑文档')
  })

  it('adapts the reader to its available workspace width', () => {
    expect(source).toContain('container-type: inline-size;')
    expect(source).toContain('@container (max-width: 1040px)')
    expect(source).toContain('@container (max-width: 720px)')
    expect(source).toContain('document-view__reading-row')
    expect(source).not.toContain('max-height: calc(100vh - 210px);')
  })

  it('provides chapter navigation at the end of a rendered section', () => {
    expect(source).toContain('class="document-view__chapter-footer"')
    expect(source).toContain('aria-label="章节导航"')
    expect(source).toContain('class="document-view__chapter-footer-select"')
    expect(source).toContain('class="document-view__chapter-footer-status"')
  })
})
