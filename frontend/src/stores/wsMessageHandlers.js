/**
 * WebSocket 消息处理器
 *
 * 从 websocket.js 的 processOtherMessage 提取。
 * 按消息 type 分发到对应的 store 操作。
 */

import { useRoomStore } from './room'
import { useChatStore } from './chat'
import { useUserStore } from './userStore'

/**
 * 处理非聊天、非 AI 流式的 WebSocket 消息
 * @param {Object} data  解析后的消息对象
 * @param {Object} wsActions  websocket store 暴露的回调 { triggerCountdownStart, triggerCountdownCancel }
 */
export function handleOtherMessage(data, wsActions = {}) {
  const chatStore = useChatStore()
  const roomStore = useRoomStore()
  const userStore = useUserStore()

  switch (data.type) {
    // ── 系统消息 ──────────────────────────────────────
    case 'system': {
      let systemContent = '系统消息'
      if (data.event === 'connected') {
        if (data.context === 'create' && data.room_name) {
          systemContent = `您已创建了"${data.room_name}"房间`
        } else if (data.context === 'join' && data.room_name) {
          systemContent = `您已加入"${data.room_name}"房间`
        } else {
          systemContent = '已连接到房间'
        }
      } else if (data.message) {
        systemContent = data.message
      } else if (data.content) {
        systemContent = data.content
      }
      chatStore.addMessage({
        is_system: true,
        content: systemContent,
        timestamp: data.timestamp || Date.now()
      })
      break
    }

    case 'secret':
      chatStore.addSecretMessage(data)
      break

    // ── 用户列表 ─────────────────────────────────────
    case 'user_list_update':
      if (data.users && Array.isArray(data.users)) {
        console.log(`[WS] 收到用户列表更新: ${data.users.length} 名用户`)
        roomStore.updateUserList(data.users)
      } else {
        console.warn('[WS] 收到的用户列表更新消息格式不正确:', data)
      }
      break

    // ── 用户加入 / 离开 ──────────────────────────────
    case 'user_join':
    case 'user_leave':
    case 'host_leave':
      _handleUserPresence(data, roomStore, chatStore)
      break

    case 'user_ready':
    case 'user_ready_update':
      roomStore.updateReadyStatus(data)
      break

    // ── 游戏生命周期 ─────────────────────────────────
    case 'game_start':
      roomStore.setGameStatus(true)
      console.log('[WS] Game started!')
      break

    case 'game_end':
      _handleGameEnd(data, roomStore, chatStore)
      break

    case 'game_initialized':
      _handleGameInitialized(data, roomStore)
      break

    case 'game_phase_update':
      _handleGamePhaseUpdate(data, roomStore)
      break

    // ── 倒计时 ───────────────────────────────────────
    case 'countdown_start':
      console.log('[WS] 倒计时开始:', data)
      if (wsActions.triggerCountdownStart) {
        wsActions.triggerCountdownStart(data.duration || 5)
      }
      break

    case 'countdown_cancelled':
      console.log('[WS] 倒计时取消:', data)
      if (wsActions.triggerCountdownCancel) {
        wsActions.triggerCountdownCancel(data.reason || '倒计时已取消')
      }
      break

    // ── 房主变更 ─────────────────────────────────────
    case 'new_host':
      if (data.new_host_id) {
        roomStore.setHost(data.new_host_id)
      }
      break

    // ── 上帝角色相关 ─────────────────────────────────
    case 'god_role_inquiry':
      roomStore.setGodPollingStatus(true)
      console.log('[WS] 收到上帝角色询问:', data)
      roomStore.setGodRoleInquiry(true, data.message, data.timeout)
      break

    case 'god_role_inquiry_status':
      roomStore.setGodPollingStatus(true)
      console.log('[WS] 收到上帝角色询问状态:', data)
      roomStore.handleGodRoleInquiryStatus(data)
      break

    case 'god_role_assigned':
      console.log('[WS] 上帝角色已分配:', data)
      roomStore.setGodRoleInquiry(false)
      if (data.is_ai) {
        roomStore.showToast('info', '没有玩家愿意担任上帝，本局游戏将由AI担任上帝角色')
      } else {
        roomStore.showToast('success', '已选定上帝角色')
      }
      break

    case 'you_are_god':
      console.log('[WS] 您被选为上帝角色')
      roomStore.showToast('success', '您已被选为本局游戏的上帝')
      break

    case 'god_words_selection':
      console.log('[WS] 收到上帝选词消息:', data)
      document.dispatchEvent(new CustomEvent('god-words-selection', { detail: data }))
      break

    case 'god_words_selected':
      console.log('[WS] 上帝选词完成:', data)
      document.dispatchEvent(new CustomEvent('god-words-selected', { detail: data }))
      break

    // ── 投票相关 ─────────────────────────────────────
    case 'player_voted':
      _handlePlayerVoted(data, roomStore)
      break

    case 'vote_cast':
      _handleVoteCast(data, roomStore, chatStore)
      break

    case 'vote_phase_start':
      _handleVotePhaseStart(data, roomStore, chatStore)
      break

    case 'vote_result':
      _handleVoteResult(data, roomStore, chatStore)
      break

    // ── 玩家淘汰 ─────────────────────────────────────
    case 'player_eliminated':
      _handlePlayerEliminated(data, roomStore, userStore)
      break

    // ── 角色分配 ─────────────────────────────────────
    case 'role_word_assignment':
      _handleRoleWordAssignment(data, roomStore)
      break

    // ── 发言轮次 ─────────────────────────────────────
    case 'speaking_turn':
      console.log('[WS] 收到发言轮次消息:', data)
      document.dispatchEvent(new CustomEvent('speaking-turn', { detail: data }))
      if (data.message) {
        chatStore.addMessage({
          is_system: true,
          content: data.message,
          timestamp: data.timestamp || Date.now()
        })
      }
      break

    // ── 遗言阶段 ─────────────────────────────────────
    case 'last_words_start':
      _handleLastWordsStart(data, roomStore, chatStore)
      break

    case 'last_words_phase_end':
      _handleLastWordsEnd(data, roomStore, chatStore)
      break

    default:
      console.warn('[WS] 未处理的消息类型:', data.type)
  }
}

// ── 私有辅助函数 ──────────────────────────────────────

function _handleUserPresence(data, roomStore, chatStore) {
  console.log(`[WS] 收到${data.type === 'user_join' ? '用户加入' : (data.type === 'host_leave' ? '房主离开' : '用户离开')}消息:`, data)

  if (data.type === 'user_join') {
    if (data.user_id && data.username) {
      roomStore.addUser({
        id: data.user_id,
        username: data.username,
        avatar_url: data.avatar_url || '/default_avatar.jpg',
        status: 'in_room'
      })
    }
  } else if (data.type === 'user_leave') {
    if (data.user_id) roomStore.removeUser(data.user_id)
  } else if (data.type === 'host_leave') {
    if (data.user_id) {
      roomStore.removeUser(data.user_id)
      if (data.new_host_id) roomStore.setHost(data.new_host_id)
    }
  }

  if (data.content) {
    chatStore.addMessage({
      is_system: true,
      content: data.content,
      timestamp: data.timestamp || Date.now()
    })
  }
}

function _handleGameEnd(data, roomStore, chatStore) {
  console.log('[WS] 游戏结束:', data)
  roomStore.setGameStatus(false)

  const winningRoleName = data.winning_role === 'civilian' ? '平民' : '卧底'
  chatStore.addMessage({
    is_system: true,
    content: `游戏结束，${winningRoleName}阵营获胜！`,
    timestamp: data.timestamp || Date.now()
  })

  if (data.roles) {
    Object.entries(data.roles).forEach(([playerId, role]) => {
      roomStore.handlePlayerEliminated(playerId, role)
    })
  }

  document.dispatchEvent(new CustomEvent('game-result', { detail: data }))
}

function _handleGameInitialized(data, roomStore) {
  console.log('[WS] 游戏初始化完成')

  if (data.current_phase) {
    roomStore.updateGamePhase(data.current_phase)
  } else {
    roomStore.updateGamePhase('speaking')
  }

  if (data.current_round) {
    roomStore.updateGameRound(data.current_round)
  } else {
    roomStore.updateGameRound(1)
  }

  roomStore.setGodPollingStatus(false)
  document.dispatchEvent(new CustomEvent('game-initialized', { detail: data }))
}

function _handleGamePhaseUpdate(data, roomStore) {
  console.log('[WS] 游戏阶段更新:', data)
  if (data.phase) roomStore.updateGamePhase(data.phase)
  if (data.round) roomStore.updateGameRound(data.round)
  if (roomStore.isGodPolling) roomStore.setGodPollingStatus(false)
}

function _handlePlayerVoted(data, roomStore) {
  console.log('[WS] 收到玩家投票消息:', data)
  if (data.vote_count) roomStore.updateVoteCount(data.vote_count)
  if (data.voter_id && data.target_id) roomStore.recordVote(data.voter_id, data.target_id)
}

function _handleVoteCast(data, roomStore, chatStore) {
  console.log('[WS] 收到投票事件消息:', data)
  if (data.voter_id && data.target_id) {
    roomStore.recordVote(data.voter_id, data.target_id)
    chatStore.addMessage({
      is_system: true,
      content: `${data.voter_name || '玩家'} 投票给了 ${data.target_name || '目标玩家'}`,
      timestamp: data.timestamp || Date.now()
    })
    if (data.vote_count) {
      roomStore.updateVoteCount(data.vote_count)
    } else {
      const voteCount = { ...roomStore.voteCount }
      voteCount[data.target_id] = (voteCount[data.target_id] || 0) + 1
      roomStore.updateVoteCount(voteCount)
    }
  }
}

function _handleVotePhaseStart(data, roomStore, chatStore) {
  console.log('[WS] 投票阶段开始:', data)
  roomStore.clearVotes()
  roomStore.updateGamePhase('voting')
  if (!roomStore.gameStarted) roomStore.gameStarted = true
  if (data.current_round) roomStore.updateGameRound(data.current_round)

  chatStore.addMessage({
    is_system: true,
    content: `投票阶段开始，请选择你怀疑的玩家进行投票。投票时间：${data.vote_timeout || 10}秒`,
    timestamp: data.timestamp || Date.now()
  })

  document.dispatchEvent(new CustomEvent('vote-phase-start', { detail: data }))
}

function _handleVoteResult(data, roomStore, chatStore) {
  console.log('[WS] 投票结果:', data)
  roomStore.clearVotes()
  if (data.result === 'tie') {
    chatStore.addMessage({
      is_system: true,
      content: data.message || '投票结束，没有玩家被淘汰',
      timestamp: data.timestamp || Date.now()
    })
    roomStore.showToast('info', data.message || '投票结束，没有玩家被淘汰')
  }
}

function _handlePlayerEliminated(data, roomStore, userStore) {
  console.log('[WS] 收到玩家被淘汰消息:', data)
  if (data.player_id && data.role) {
    roomStore.handlePlayerEliminated(data.player_id, data.role)

    if (userStore.user && data.player_id === userStore.user.id) {
      roomStore.showToast('warning', '你已被淘汰，但仍可以观看游戏进行')
      document.dispatchEvent(new CustomEvent('current-player-eliminated', {
        detail: { playerId: data.player_id, role: data.role }
      }))
    }

    if (roomStore.gamePhase === 'voting') {
      roomStore.updateGamePhase('last_words')
    }
  }
}

function _handleRoleWordAssignment(data, roomStore) {
  console.log('[WS] 收到角色和词语分配消息:', data)

  if (data.role) {
    if (!data.roles) data.roles = {}
    const userStore = useUserStore()
    const currentUserId = userStore.user?.id
    if (currentUserId) data.roles[currentUserId] = data.role

    if (data.role === 'civilian' && data.word) {
      data.civilian_word = data.word
    } else if (data.role === 'spy' && data.word) {
      data.spy_word = data.word
    }
  }

  if (data.god_id) {
    if (!data.roles) data.roles = {}
    data.roles[data.god_id] = 'god'
  }

  roomStore.setRoleInfo(data)

  if (roomStore.isGodPolling) roomStore.setGodPollingStatus(false)

  if (!data.current_phase && roomStore.gamePhase === '') {
    roomStore.updateGamePhase('speaking')
  }

  document.dispatchEvent(new CustomEvent('role-assigned', { detail: data }))
}

function _handleLastWordsStart(data, roomStore, chatStore) {
  console.log('[WS] 遗言阶段开始:', data)
  roomStore.updateGamePhase('last_words')
  chatStore.addMessage({
    is_system: true,
    content: `${data.player_name || '玩家'} 进入遗言阶段，时间：${data.timeout || 10}秒`,
    timestamp: data.timestamp || Date.now()
  })
  roomStore.setLastWordsPlayerId(data.player_id)

  const userStore = useUserStore()
  if (data.player_id === userStore.user?.id) {
    roomStore.setCanSpeakInLastWords(true)
  }

  document.dispatchEvent(new CustomEvent('last-words-phase-start', { detail: data }))
}

function _handleLastWordsEnd(data, roomStore, chatStore) {
  console.log('[WS] 遗言阶段结束:', data)
  if (roomStore.gamePhase === 'last_words') {
    roomStore.clearLastWordsState()
    chatStore.addMessage({
      is_system: true,
      content: '遗言阶段结束',
      timestamp: data.timestamp || Date.now()
    })
  }
}
