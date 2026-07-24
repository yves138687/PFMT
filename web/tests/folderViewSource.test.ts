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
  })

  it('wires directory creation plus move and delete actions', () => {
    expect(source).toContain('@click="openCreateFolder"')
    expect(source).toContain('@click="openMovePath"')
    expect(source).toContain('@click="deleteCurrentPath"')
    expect(source).toContain('@click="openMoveFile(row)"')
    expect(source).toContain('@click="deleteFile(row)"')
  })

  it('does not expose private directory type in create folder dialog', () => {
    expect(source).not.toContain('目录类型')
    expect(source).not.toContain('私密')
  })
})
