import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverStub)
vi.stubGlobal(
  'fetch',
  vi.fn(async () => {
    throw new Error('API intentionally unavailable in isolated UI tests')
  }),
)

afterEach(() => {
  cleanup()
})
