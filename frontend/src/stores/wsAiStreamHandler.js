/**
 * AI 流式消息处理器
 *
 * 从 websocket.js 提取的 AI 相关消息处理逻辑：
 * - processAiStreamMessage  (真实流式)
 * - simulateAiStream        (模拟流式，用于 AI 玩家的普通消息/遗言)
 * - getAiPlayerInfo          (辅助：获取 AI 玩家信息)
 */

import { useRoomStore } from './room'
import { useChatStore } from './chat'

/**
 * 获取 AI 玩家的用户名和头像
 * @param {string} userId  AI 玩家 ID，如 llm_player_1
 * @returns {{ username: string, avatarUrl: string }}
 */
export function getAiPlayerInfo(userId) {
    const roomStore = useRoomStore()

    const defaultInfo = {
        username: 'AI玩家',
        avatarUrl: '/default_room_robot_avatar.jpg'
    }

    if (!userId || !userId.startsWith('llm_player_')) {
        return defaultInfo
    }

    const aiNumber = userId.replace('llm_player_', '')
    defaultInfo.username = `AI玩家_${aiNumber}`

    // 从 roomStore 用户列表中查找
    const aiPlayer = roomStore.users.find(u => u.id === userId)
    if (aiPlayer) {
        return {
            username: aiPlayer.username || defaultInfo.username,
            avatarUrl: aiPlayer.avatar_url || defaultInfo.avatarUrl
        }
    }

    // 检查 Redis 中分配的 AI 头像
    if (roomStore.roomInfo && roomStore.roomInfo.invite_code) {
        const aiAvatar = roomStore.getAiAvatarById(userId)
        if (aiAvatar) {
            defaultInfo.avatarUrl = aiAvatar
        }
    }

    return defaultInfo
}

/**
 * 模拟流式输出效果（用于 AI 普通消息和遗言）
 * @param {Object} data            消息数据
 * @param {Map}    activeAiSessions 活跃 AI 会话 Map
 * @returns {string}               会话 ID
 */
export function simulateAiStream(data, activeAiSessions) {
    const chatStore = useChatStore()
    const prefix = data.type === 'last_words' ? 'ai_lastwords' : 'ai_message'
    const sessionId = `${prefix}_${Date.now()}`
    const aiPlayerInfo = getAiPlayerInfo(data.user_id)

    const sessionData = {
        content: data.content || '',
        updateTimer: null,
        lastUpdateTime: Date.now(),
        needsUpdate: true,
        isStreaming: true,
        timestamp: data.timestamp || Date.now()
    }
    activeAiSessions.set(sessionId, sessionData)

    // 添加初始空消息
    chatStore.addMessage({
        id: sessionId,
        type: 'ai_stream',
        username: data.username || aiPlayerInfo.username,
        user_id: data.user_id,
        timestamp: sessionData.timestamp,
        content: '',
        isStreaming: true,
        avatarUrl: data.avatar_url || aiPlayerInfo.avatarUrl
    })

    // 分段输出
    let currentIndex = 0
    const content = data.content || ''
    const chunkSize = Math.max(3, Math.floor(content.length / 10))

    sessionData.updateTimer = setInterval(() => {
        if (currentIndex < content.length) {
            const nextIndex = Math.min(currentIndex + chunkSize, content.length)
            sessionData.content = content.substring(0, nextIndex)
            currentIndex = nextIndex

            chatStore.updateAiStreamMessage(sessionId, {
                content: sessionData.content,
                isStreaming: currentIndex < content.length
            })

            if (currentIndex >= content.length) {
                sessionData.isStreaming = false
                clearInterval(sessionData.updateTimer)
                sessionData.updateTimer = null
                setTimeout(() => { activeAiSessions.delete(sessionId) }, 1000)
            }
        }
    }, 100)

    return sessionId
}

/**
 * 处理真实 AI 流式消息（后端分片推送）
 * @param {Object} data            消息数据
 * @param {Map}    activeAiSessions 活跃 AI 会话 Map
 */
export function processAiStreamMessage(data, activeAiSessions) {
    const sessionId = data.session_id
    if (!sessionId) {
        console.error('[WS] AI stream message missing session_id:', data)
        return
    }

    const chatStore = useChatStore()
    const roomStore = useRoomStore()
    let sessionData = activeAiSessions.get(sessionId)

    // ── 开始消息 ──
    if (data.is_start) {
        if (!sessionData) {
            sessionData = {
                content: data.content || '',
                updateTimer: null,
                lastUpdateTime: Date.now(),
                needsUpdate: true,
                isStreaming: true,
                timestamp: data.timestamp || Date.now()
            }
            activeAiSessions.set(sessionId, sessionData)

            // 解析 AI 玩家信息
            let username = 'AI助理'
            let avatarUrl = '/default_room_robot_avatar.jpg'

            if (data.user_id && data.user_id.startsWith('llm_player_')) {
                const info = getAiPlayerInfo(data.user_id)
                username = info.username
                avatarUrl = info.avatarUrl

                // 额外检查 Redis 分配的头像
                if (roomStore.roomInfo && roomStore.roomInfo.invite_code) {
                    const redisAvatar = roomStore.getAiAvatarById(data.user_id)
                    if (redisAvatar) avatarUrl = redisAvatar
                }
            }

            chatStore.addMessage({
                id: sessionId,
                type: 'ai_stream',
                username,
                user_id: data.user_id || 'ai_assistant',
                timestamp: sessionData.timestamp,
                content: sessionData.content,
                isStreaming: true,
                avatarUrl
            })
        } else {
            // 会话已存在，重置
            sessionData.content = data.content || ''
            sessionData.isStreaming = true
            sessionData.needsUpdate = true
            sessionData.timestamp = data.timestamp || Date.now()
            chatStore.updateAiStreamMessage(sessionId, {
                content: sessionData.content,
                isStreaming: true
            })
        }
        return
    }

    // ── 数据更新 / 结束 ──
    if (!sessionData) {
        console.warn(`[WS] Received stream data for unknown session: ${sessionId}`)
        return
    }

    if (data.content !== undefined) {
        sessionData.content += data.content
        sessionData.needsUpdate = true
    }

    if (data.is_end) {
        sessionData.isStreaming = false
        sessionData.needsUpdate = true
        if (sessionData.updateTimer) {
            clearInterval(sessionData.updateTimer)
            sessionData.updateTimer = null
        }
        chatStore.updateAiStreamMessage(sessionId, {
            content: sessionData.content,
            isStreaming: false
        })
        setTimeout(() => { activeAiSessions.delete(sessionId) }, 1000)
        return
    }

    // 定时刷新 UI
    if (!sessionData.updateTimer) {
        sessionData.updateTimer = setInterval(() => {
            if (sessionData.needsUpdate) {
                chatStore.updateAiStreamMessage(sessionId, {
                    content: sessionData.content,
                    isStreaming: sessionData.isStreaming
                })
                sessionData.lastUpdateTime = Date.now()
                sessionData.needsUpdate = false
            }
        }, 100)
    }
}
