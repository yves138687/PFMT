import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

import FileUploadDialog from '@/components/FileUploadDialog.vue'
import { useSettingsStore } from '@/stores/settingsStore'

const source = readFileSync(
  resolve(process.cwd(), 'src/components/FileUploadDialog.vue'),
  'utf-8'
)

const dialogStub = {
  props: ['modelValue'],
  template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>'
}

describe('FileUploadDialog source contract', () => {
  it('uploads directly to the provided current folder without a path selector', () => {
    expect(source).toContain('targetPathId')
    expect(source).toContain('pathId: props.targetPathId')
    expect(source).toContain('上传到：{{ targetFullPath }}')
    expect(source).not.toContain('<el-select')
  })

  it('uses a mobile-compatible file chooser and queue layout', () => {
    expect(source).toContain(':close-on-click-modal="false"')
    expect(source).toContain('width="min(760px, calc(100vw - 24px))"')
    expect(source).toContain('file-upload-dialog__input')
    expect(source).toContain('file-upload-dialog__queue-list')
    expect(source).toContain('globalThis.crypto?.randomUUID')
    expect(source).not.toContain('class="hidden-input"')
  })

  it('keeps selected files in the dialog after input change without crypto.randomUUID', async () => {
    vi.stubGlobal('crypto', {})
    setActivePinia(createPinia())
    const settingsStore = useSettingsStore()
    settingsStore.initialized = true

    const wrapper = mount(FileUploadDialog, {
      props: {
        modelValue: true,
        targetPathId: 'root',
        targetFullPath: '/'
      },
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-dialog': dialogStub,
          'el-empty': { template: '<div>上传队列为空</div>' },
          'el-icon': { template: '<span><slot /></span>' },
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div />' },
          'el-tag': { template: '<span><slot /></span>' }
        }
      }
    })

    const input = wrapper.find('input[type="file"]')
    const file = new File(['hello'], 'mobile-note.txt', {
      type: 'text/plain',
      lastModified: 1
    })
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })

    await input.trigger('change')

    expect(wrapper.text()).toContain('mobile-note.txt')
    expect(wrapper.text()).toContain('待上传')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
