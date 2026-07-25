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
    expect(source).toContain('@click="openEditPath"')
    expect(source).toContain('@click="openMovePath"')
    expect(source).toContain('@click="deleteCurrentPath"')
    expect(source).toContain('@selection-change="handleSelectionChange"')
    expect(source).toContain('@click="openMoveSelectedFiles"')
    expect(source).toContain('@click="toggleFileHidden(row)"')
    expect(source).toContain('@click="deleteFile(row)"')
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

  it('supports merging selected documents into a new file', () => {
    expect(source).toContain('合并文档')
    expect(source).toContain('openMergeSelectedDocuments')
    expect(source).toContain('mergeSelectedDocuments')
    expect(source).toContain('filesApi.mergeDocuments')
    expect(source).toContain('selectedDocumentFiles')
    expect(source).toContain('按原始文件名升序合并')
    expect(source).toContain("name: 'document'")
  })

  it('offers local metadata filters without exposing hidden content by default', () => {
    expect(source).toContain('筛选文件名、备注、摘要')
    expect(source).toContain('标签筛选')
    expect(source).toContain('settingsStore.showHiddenContent')
  })

  it('does not expose private directory type in create folder dialog', () => {
    expect(source).not.toContain('目录类型')
    expect(source).not.toContain('私密')
  })
})
