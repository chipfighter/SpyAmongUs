/**
 * Unit tests for the room Pinia store (useRoomStore).
 *
 * These tests exercise synchronous state helpers; API / WebSocket
 * calls are not tested here.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRoomStore } from '@/stores/room'

describe('roomStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  // -- default state --

  it('has sensible defaults', () => {
    const store = useRoomStore()
    expect(store.gameStarted).toBe(false)
    expect(store.isCurrentUserReady).toBe(false)
    expect(store.users).toEqual([])
    expect(store.currentRound).toBe(1)
    expect(store.gamePhase).toBe('speaking')
  })

  it('roomInfo starts empty', () => {
    const store = useRoomStore()
    expect(store.roomInfo.invite_code).toBeNull()
    expect(store.roomInfo.host_id).toBeNull()
  })

  // -- state mutation helpers (if exposed as actions) --

  it('can set roomInfo fields', () => {
    const store = useRoomStore()
    store.roomInfo = {
      name: 'TestRoom',
      invite_code: 'ABC12345',
      host_id: 'usr_host',
      status: 'waiting',
      total_players: 6,
    }
    expect(store.roomInfo.name).toBe('TestRoom')
    expect(store.roomInfo.total_players).toBe(6)
  })

  it('can toggle ready state', () => {
    const store = useRoomStore()
    expect(store.isCurrentUserReady).toBe(false)
    store.isCurrentUserReady = true
    expect(store.isCurrentUserReady).toBe(true)
  })

  it('tracks users list', () => {
    const store = useRoomStore()
    store.users = [
      { id: 'usr_1', username: 'alice' },
      { id: 'usr_2', username: 'bob' },
    ]
    expect(store.users).toHaveLength(2)
  })

  // -- game phase transitions --

  it('tracks game phase', () => {
    const store = useRoomStore()
    store.gamePhase = 'voting'
    expect(store.gamePhase).toBe('voting')
  })

  it('tracks round number', () => {
    const store = useRoomStore()
    store.currentRound = 3
    expect(store.currentRound).toBe(3)
  })

  // -- vote state --

  it('voteCount starts empty', () => {
    const store = useRoomStore()
    expect(store.voteCount).toEqual({})
  })

  it('votedPlayers starts empty', () => {
    const store = useRoomStore()
    expect(store.votedPlayers).toEqual({})
  })

  // -- AI avatar mapping --

  it('aiAvatarMapping starts empty', () => {
    const store = useRoomStore()
    expect(store.aiAvatarMapping).toEqual({})
  })

  it('can set AI avatar mapping', () => {
    const store = useRoomStore()
    store.aiAvatarMapping = {
      llm_player_1: '/llm_avatar_3.png',
      llm_player_2: '/llm_avatar_1.png',
    }
    expect(Object.keys(store.aiAvatarMapping)).toHaveLength(2)
  })
})
