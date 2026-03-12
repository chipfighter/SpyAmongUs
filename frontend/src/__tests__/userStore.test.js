/**
 * Unit tests for the user Pinia store (userStore).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/userStore'

describe('userStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  // -- initial state --

  it('starts unauthenticated', () => {
    const store = useUserStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(store.accessToken).toBeNull()
  })

  it('default avatar when user is null', () => {
    const store = useUserStore()
    expect(store.userAvatar).toBe('/default_avatar.jpg')
  })

  // -- initStore --

  it('restores state from localStorage', () => {
    localStorage.setItem('accessToken', 'tok123')
    localStorage.setItem('refreshToken', 'ref456')
    localStorage.setItem('userData', JSON.stringify({ id: 'usr_1', username: 'alice' }))

    const store = useUserStore()
    store.initStore()

    expect(store.isAuthenticated).toBe(true)
    expect(store.user.username).toBe('alice')
  })

  it('does not restore if token missing', () => {
    localStorage.setItem('userData', JSON.stringify({ id: 'usr_1' }))

    const store = useUserStore()
    store.initStore()

    expect(store.isAuthenticated).toBe(false)
  })

  // -- clearUserData --

  it('clears all auth state', () => {
    const store = useUserStore()
    store.accessToken = 'tok'
    store.refreshToken = 'ref'
    store.user = { id: 'usr_1', username: 'bob' }

    store.clearUserData()

    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(localStorage.removeItem).toHaveBeenCalled()
  })

  // -- saveUserData --

  it('persists tokens and user to localStorage', () => {
    const store = useUserStore()
    store.accessToken = 'access_tok'
    store.refreshToken = 'refresh_tok'
    store.user = { id: 'usr_1', username: 'carol', avatar_url: null }

    store.saveUserData()

    expect(localStorage.setItem).toHaveBeenCalledWith('accessToken', 'access_tok')
    expect(localStorage.setItem).toHaveBeenCalledWith('token', 'access_tok')
  })

  // -- updateActivityTime --

  it('updates lastActivityTime', () => {
    const store = useUserStore()
    const before = Date.now()
    store.updateActivityTime()
    expect(store.lastActivityTime).toBeGreaterThanOrEqual(before)
  })

  // -- isSessionExpired --

  it('session is not expired for recent activity', () => {
    const store = useUserStore()
    store.lastActivityTime = Date.now()
    expect(store.isSessionExpired).toBe(false)
  })

  it('session is expired after inactivity threshold', () => {
    const store = useUserStore()
    store.lastActivityTime = Date.now() - 25 * 60 * 1000
    expect(store.isSessionExpired).toBe(true)
  })
})
