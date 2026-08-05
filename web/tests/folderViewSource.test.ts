import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const source = readFileSync(
  resolve(process.cwd(), 'src/views/files/FolderView.vue'),
  'utf-8'
)

describe('FolderView source contract', () => {
  it('keeps storage internals out of the file list UI', () => {
    expect(source).not.toContain('storage_object_name')
    expect(source).not.toContain('对象名')
    expect(source).not.toContain('{{ row.file_id }}')
  })

  it('offers direct detail view and properties actions', () => {
    expect(source).toContain("name: 'file-detail'")
    expect(source).toContain('查看')
    expect(source).toContain('属性')
    expect(source).toContain("file.file_type === 'text'")
    expect(source).toContain("file.file_type === 'image'")
    expect(source).toContain("file.file_type === 'video'")
    expect(source).toContain('openImagePreview')
    expect(source).toContain('openVideoPreview')
    expect(source).toContain('issuePreviewToken')
    expect(source).toContain('class="image-viewer"')
    expect(source).toContain('class="video-viewer"')
    expect(source).toContain('<video')
    expect(source).toContain('image-viewer__thumb')
    expect(source).not.toContain('<el-carousel')
  })

  it('wires directory creation plus move and delete actions', () => {
    expect(source).toContain('@click="openCreateFolder"')
    expect(source).toContain('handlePathAction')
    expect(source).toContain("command === 'edit-path'")
    expect(source).toContain("command === 'move-path'")
    expect(source).toContain("command === 'delete-path'")
    expect(source).toContain('openEditPath()')
    expect(source).toContain('openMovePath()')
    expect(source).toContain('deleteCurrentPath()')
    expect(source).toContain('@selection-change="handleSelectionChange"')
    expect(source).toContain('@click="openMoveSelectedFiles"')
    expect(source).toContain("command === 'toggle-hidden'")
    expect(source).toContain("command === 'delete'")
    expect(source).toContain('toggleFileHidden(file)')
    expect(source).toContain('deleteFile(file)')
  })

  it('opens upload dialog for the current folder instead of navigating away', () => {
    expect(source).toContain('FileUploadDialog')
    expect(source).toContain(':target-path-id="currentPathId"')
    expect(source).toContain('@click="openUploadDialog"')
    expect(source).not.toContain("router.push({ name: 'upload' })")
  })

  it('uses batch move instead of row-level move action', () => {
    expect(source).toContain('移动所选')
    expect(source).toContain('moveSelectedFiles')
    expect(source).not.toContain('openMoveFile(row)')
  })

  it('exports selected files and offers row-level export', () => {
    expect(source).toContain('导出所选')
    expect(source).toContain('exportSelectedFiles')
    expect(source).toContain('exportSingleFile')
    expect(source).toContain('filesApi.exportFiles')
    expect(source).toContain('filesApi.exportFile')
    expect(source).toContain(':disabled="!selectedFiles.length"')
    expect(source).toContain('saveBlobResponse')
  })

  it('supports merging selected documents into a new file', () => {
    expect(source).toContain('合并文档')
    expect(source).toContain('openMergeSelectedDocuments')
    expect(source).toContain('mergeSelectedDocuments')
    expect(source).toContain('filesApi.mergeDocuments')
    expect(source).toContain('selectedDocumentFiles')
    expect(source).toContain('canMergeSelectedDocuments')
    expect(source).toContain(':disabled="!canMergeSelectedDocuments"')
    expect(source).toContain('按原始文件名升序合并')
    expect(source).toContain("name: 'document'")
  })

  it('creates blank documents from the current folder', () => {
    expect(source).toContain('@click="openCreateDocument"')
    expect(source).toContain('createDocumentVisible')
    expect(source).toContain('filesApi.createDocument')
    expect(source).toContain('创建并打开')
    expect(source).toContain('document_format')
    expect(source).toContain("name: 'document'")
  })

  it('offers local metadata filters without exposing hidden content by default', () => {
    expect(source).toContain('筛选文件名、备注、摘要')
    expect(source).toContain('类型筛选')
    expect(source).toContain('fileTypeFilter')
    expect(source).toContain('标签筛选')
    expect(source).toContain('settingsStore.showHiddenContent')
  })

  it('supports list and icon management views with shared selection', () => {
    expect(source).toContain("type FileViewMode = 'list' | 'grid'")
    expect(source).toContain('v-model="viewMode"')
    expect(source).toContain('folder-view__grid')
    expect(source).toContain('file-card')
    expect(source).toContain('folder-view__mobile-list')
    expect(source).toContain('class="file-row"')
    expect(source).toContain('toggleGridFileSelection')
    expect(source).toContain('isFileSelected(file)')
    expect(source).toContain('@selection-change="handleSelectionChange"')
    expect(source).toContain('selectedFiles.value')
  })

  it('keeps file names as the primary open target and collapses row actions', () => {
    expect(source).toContain(':aria-label="`查看${row.original_name}`"')
    expect(source).toContain('@click="openFileDetail(row)"')
    expect(source).toContain(':aria-label="`查看${file.original_name}`"')
    expect(source).toContain('@click="openFileDetail(file)"')
    expect(source).toContain('type FileActionCommand')
    expect(source).toContain('fileActionItems(file)')
    expect(source).toContain('handleFileAction(row, $event)')
    expect(source).toContain('fileActionsDrawerVisible')
    expect(source).toContain('<el-drawer')
    expect(source).toContain('<el-dropdown')
    expect(source).not.toContain('width="320"')
    expect(source).not.toContain('class="file-card__actions"')
  })

  it('uses the shared mobile breakpoint for compact toolbar and drawers', () => {
    expect(source).toContain("const MOBILE_QUERY = '(max-width: 820px)'")
    expect(source).toContain('isMobileViewport')
    expect(source).toContain('filterDrawerVisible')
    expect(source).toContain('batchActionsDrawerVisible')
    expect(source).toContain('grid-template-columns: 32px 42px minmax(0, 1fr) 40px')
    expect(source).toContain('@media (max-width: 820px)')
  })

  it('does not expose private directory type in create folder dialog', () => {
    expect(source).not.toContain('目录类型')
    expect(source).not.toContain('私密')
  })
})
