import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

configure({ asyncUtilTimeout: 5000 })

// jsdom does not implement scrolling.
window.scrollTo = () => {}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})
