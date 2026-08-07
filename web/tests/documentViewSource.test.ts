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
    expect(source).toContain('resize: none')
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
    expect(source).toContain(":disabled=\"!documentContent || mode === 'read'\"")
  })
})
