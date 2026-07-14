import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('vue-router', () => ({
  createRouter: vi.fn(() => ({ push: vi.fn(), beforeEach: vi.fn() })),
  createWebHistory: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}))

const mockAxios = vi.hoisted(() => ({
  create: vi.fn(() => ({
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    post: vi.fn(),
    get: vi.fn(),
  })),
  interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
}))

vi.mock('axios', () => ({ default: mockAxios }))

import { useAuthStore } from '../stores/auth.js'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('starts unauthenticated when no token', () => {
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.isAdmin).toBe(false)
    expect(auth.token).toBe('')
  })

  it('_saveAuth stores token and user', () => {
    const auth = useAuthStore()
    auth._saveAuth({
      access_token: 'test-token-123',
      refresh_token: 'refresh-123',
      user: { email: 'alice@example.com', role: 'admin' },
    })
    expect(auth.token).toBe('test-token-123')
    expect(auth.refreshToken).toBe('refresh-123')
    expect(auth.user.email).toBe('alice@example.com')
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.isAdmin).toBe(true)
  })

  it('logout clears state and redirects', () => {
    const auth = useAuthStore()
    auth._saveAuth({ access_token: 'tok', user: { role: 'admin' } })
    auth.logout()
    expect(auth.token).toBe('')
    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('aziza_token')).toBeNull()
  })

  it('isAdmin is false for non-admin roles', () => {
    const auth = useAuthStore()
    auth._saveAuth({ access_token: 'tok', user: { role: 'user' } })
    expect(auth.isAdmin).toBe(false)
  })
})
