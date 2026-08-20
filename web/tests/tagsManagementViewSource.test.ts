import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const source = readFileSync(resolve(process.cwd(), 'src/views/tags/TagsManagementView.vue'), 'utf-8')
const routerSource = readFileSync(resolve(process.cwd(), 'src/router/index.ts'), 'utf-8')
const topNavigationSource = readFileSync(resolve(process.cwd(), 'src/components/TopNavigation.vue'), 'utf-8')
const folderViewSource = readFileSync(resolve(process.cwd(), 'src/views/files/FolderView.vue'), 'utf-8')

describe('TagsManagementView source contract', () => {
  it('registers a first-level tag management route and navigation entries', () => {
    expect(routerSource).toContain("path: 'tags'")
    expect(routerSource).toContain("name: 'tags'")
    expect(routerSource).toContain('TagsManagementView.vue')
    expect(topNavigationSource).toContain('标签管理')
    expect(topNavigationSource).toContain("navigate('tags')")
    expect(folderViewSource).toContain('openTagManagement')
    expect(folderViewSource).toContain('CollectionTag')
  })

  it('loads visible tag usage and associated files', () => {
    expect(source).toContain('tagsApi.listTags({ withUsage: true, includeUnused: true })')
    expect(source).toContain('tagsApi.listTagFiles')
    expect(source).toContain('file_count')
    expect(source).toContain('settingsStore.showHiddenContent')
    expect(source).toContain('关联文章')
  })

  it('supports create edit delete and batch import workflows', () => {
    expect(source).toContain('tagsApi.createTag')
    expect(source).toContain('tagsApi.updateTag')
    expect(source).toContain('tagsApi.deleteTag')
    expect(source).toContain('tagsApi.importTags')
    expect(source).toContain('批量导入')
    expect(source).toContain('custom_delimiter')
    expect(source).toContain('comma_cn')
    expect(source).toContain('slash')
    expect(source).toContain('确认导入')
  })
})
