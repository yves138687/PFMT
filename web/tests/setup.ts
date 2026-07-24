import { afterEach, vi } from 'vitest'

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  }
}))

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})
