/**
 * Unit tests for Vue Router navigation guards.
 *
 * These tests do NOT mount real components; they only exercise the
 * beforeEach guard logic by simulating localStorage state.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

function buildRouter() {
  const Stub = { template: '<div />' }
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', name: 'login', component: Stub },
      { path: '/register', name: 'register', component: Stub },
      { path: '/lobby', name: 'lobby', component: Stub, meta: { requiresAuth: true } },
      { path: '/room/:roomId', name: 'room', component: Stub, meta: { requiresAuth: true } },
      { path: '/profile', name: 'profile', component: Stub, meta: { requiresAuth: true } },
      { path: '/admin', name: 'admin', component: Stub, meta: { requiresAuth: true, requiresAdmin: true } },
    ],
  })
}

function installGuard(router) {
  router.beforeEach((to, from, next) => {
    const isAuthenticated = localStorage.getItem('token')
    const userDataStr = localStorage.getItem('userData')
    const isAdmin = userDataStr ? JSON.parse(userDataStr)?.is_admin : false

    if (to.matched.some((r) => r.meta.requiresAuth) && !isAuthenticated) {
      next('/login')
    } else if (to.matched.some((r) => r.meta.requiresAdmin) && !isAdmin) {
      next('/lobby')
    } else if ((to.path === '/login' || to.path === '/register') && isAuthenticated) {
      if (isAdmin) {
        next('/admin')
      } else {
        next('/lobby')
      }
    } else {
      next()
    }
  })
}

describe('Router guards', () => {
  let router

  beforeEach(() => {
    localStorage.clear()
    router = buildRouter()
    installGuard(router)
  })

  it('redirects unauthenticated user from /lobby to /login', async () => {
    await router.push('/lobby')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows authenticated user to access /lobby', async () => {
    localStorage.setItem('token', 'fake_jwt')
    await router.push('/lobby')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/lobby')
  })

  it('redirects non-admin from /admin to /lobby', async () => {
    localStorage.setItem('token', 'fake_jwt')
    localStorage.setItem('userData', JSON.stringify({ is_admin: false }))
    await router.push('/admin')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/lobby')
  })

  it('allows admin to access /admin', async () => {
    localStorage.setItem('token', 'fake_jwt')
    localStorage.setItem('userData', JSON.stringify({ is_admin: true }))
    await router.push('/admin')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/admin')
  })

  it('redirects authenticated user from /login to /lobby', async () => {
    localStorage.setItem('token', 'fake_jwt')
    localStorage.setItem('userData', JSON.stringify({ is_admin: false }))
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/lobby')
  })

  it('redirects admin from /login to /admin', async () => {
    localStorage.setItem('token', 'fake_jwt')
    localStorage.setItem('userData', JSON.stringify({ is_admin: true }))
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/admin')
  })

  it('redirects unauthenticated user from /profile to /login', async () => {
    await router.push('/profile')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
