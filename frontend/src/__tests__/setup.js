/**
 * Vitest global test setup.
 *
 * Provides a minimal localStorage / sessionStorage shim so that
 * Pinia stores and router guards work inside jsdom.
 */

import { vi } from 'vitest'

const storageMock = () => {
  let store = {}
  return {
    getItem: vi.fn((key) => store[key] ?? null),
    setItem: vi.fn((key, value) => { store[key] = String(value) }),
    removeItem: vi.fn((key) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
    get length() { return Object.keys(store).length },
    key: vi.fn((i) => Object.keys(store)[i] ?? null),
  }
}

Object.defineProperty(globalThis, 'localStorage', { value: storageMock() })
Object.defineProperty(globalThis, 'sessionStorage', { value: storageMock() })
