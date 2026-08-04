import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const layoutSource = readFileSync(resolve(process.cwd(), 'src/layouts/MainLayout.vue'), 'utf-8')
const directoryTreeSource = readFileSync(resolve(process.cwd(), 'src/components/DirectoryTree.vue'), 'utf-8')
const topNavigationSource = readFileSync(resolve(process.cwd(), 'src/components/TopNavigation.vue'), 'utf-8')

describe('MainLayout mobile source contract', () => {
  it('uses a drawer-style directory tree on mobile', () => {
    expect(layoutSource).toContain("const MOBILE_QUERY = '(max-width: 820px)'")
    expect(layoutSource).toContain('const sidebarCollapsed = ref(isMobileViewport.value)')
    expect(layoutSource).toContain('main-layout__scrim')
    expect(layoutSource).toContain('main-layout--mobile-sidebar-open')
    expect(layoutSource).toContain('@navigate="closeMobileSidebar"')
    expect(layoutSource).toContain('width: min(var(--pfmt-sidebar-width), calc(100vw - 48px))')
  })

  it('closes the mobile directory drawer after navigation actions', () => {
    expect(directoryTreeSource).toContain('defineEmits')
    expect(directoryTreeSource).toContain('emit(\'navigate\')')
    expect(directoryTreeSource).toContain('function openSettings')
  })

  it('keeps a mobile entry for toggling hidden content', () => {
    expect(topNavigationSource).toContain('top-nav__mobile-hidden-switch')
    expect(topNavigationSource).toContain('handleShowHiddenChange')
    expect(topNavigationSource).toContain('显示隐藏内容')
    expect(topNavigationSource).toContain('.top-nav__user strong')
    expect(topNavigationSource).toContain('display: none')
  })
})
