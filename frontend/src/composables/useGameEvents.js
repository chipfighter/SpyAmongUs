/**
 * 游戏事件处理 composable
 *
 * 从 RoomView.vue 提取的游戏阶段相关事件处理逻辑：
 * - 上帝角色询问 / 选词
 * - 发言轮次
 * - 投票
 * - 游戏结算
 *
 * 使用方法：在 RoomView 的 methods 中调用这些函数，
 * 传入所需的 this 上下文属性即可。
 */

import { useNotification } from './useNotification'

const { showNotification } = useNotification()

// ── 上帝角色 ──────────────────────────────────────

/**
 * 处理上帝角色询问事件
 */
export function handleGodRoleInquiryEvent(vm, event) {
    const { visible, message, timeout } = event.detail
    vm.showGodRoleInquiry = visible
    if (visible) {
        vm.godRoleInquiryMessage = message || '您愿意担任本局游戏的上帝吗？'
        vm.godRoleInquiryTimeout = timeout || 7
    }
}

/**
 * 处理上帝角色询问状态事件（广播给其他玩家）
 */
export function handleGodRoleInquiryStatusEvent(vm, event) {
    const { visible, message, timeout, username } = event.detail
    vm.showGodRoleInquiryStatus = visible
    if (visible) {
        vm.godRoleInquiryStatusMessage = message || '正在询问玩家是否愿意担任上帝...'
        vm.godRoleInquiryStatusTimeout = timeout || 7
        vm.godRoleInquiryStatusUsername = username || ''
    }
}

/**
 * 处理上帝选词事件
 */
export function handleGodWordSelectionEvent(vm, event) {
    vm.showGodRoleInquiry = false
    vm.showGodRoleInquiryStatus = false

    setTimeout(() => {
        const data = event.detail
        if (!data.god_user_id) {
            vm.showGodWordSelection = true
            vm.godWordSelectionMessage = data.message || '请选择双方词语。'
            vm.godWordSelectionTimeout = data.timeout || 30
        } else {
            vm.showGodWordSelectionStatus = true
            vm.godWordSelectionStatusMessage = data.message || '正在选词。'
            vm.godWordSelectionStatusTimeout = data.timeout || 30
            vm.godWordSelectionStatusUsername = data.username || ''
        }
    }, 150)
}

/**
 * 处理上帝选词完成事件
 */
export function handleGodWordsSelectedEvent(vm, event) {
    vm.showGodRoleInquiry = false
    vm.showGodRoleInquiryStatus = false
    vm.showGodWordSelection = false
    vm.showGodWordSelectionStatus = false

    vm.showGameLoading = true
    vm.gameLoadingTitle = '游戏初始化中'
    vm.gameLoadingMessage = '正在等待服务器初始化游戏...'
}

/**
 * 处理上帝选词确认（用户作为上帝提交词语）
 */
export function handleGodWordSelectionConfirm(vm, wordsData) {
    vm.websocketStore.sendMessage({
        type: 'god_words_selected',
        civilian_word: wordsData.teamOne[0],
        spy_word: wordsData.teamTwo[0]
    })
    vm.showGodWordSelection = false
    vm.showGameLoading = true
    vm.gameLoadingTitle = '游戏初始化中'
    vm.gameLoadingMessage = '正在等待服务器初始化游戏...'
}

/**
 * 处理上帝选词超时
 */
export function handleGodWordSelectionTimeout(vm) {
    vm.websocketStore.sendMessage({ type: 'god_words_selection_timeout' })
    vm.showGodWordSelection = false
    showNotification('warning', '选词超时！系统将重新询问上帝角色...')
}

// ── 游戏初始化 ────────────────────────────────────

/**
 * 处理游戏初始化完成事件
 */
export function handleGameInitializedEvent(vm, event) {
    vm.showGameLoading = false
    vm.gameStartTimestamp = Date.now()
    showNotification('success', '游戏已初始化完成，游戏开始！')
}

/**
 * 处理角色分配事件
 */
export function handleRoleAssignedEvent(vm, event) {
    const { role, civilian_word, spy_word, word } = event.detail

    vm.showGodRoleInquiry = false
    vm.showGodRoleInquiryStatus = false
    vm.showGodWordSelection = false
    vm.showGodWordSelectionStatus = false
    vm.showGameLoading = false
    vm.gameStarted = true

    let roleText = ''
    if (role === 'spy') roleText = '卧底'
    else if (role === 'civilian') roleText = '平民'
    else if (role === 'god') roleText = '上帝'

    let wordText = ''
    if (role === 'spy' && (spy_word || word)) {
        wordText = `，您的词语是：${spy_word || word}`
    } else if (role === 'civilian' && (civilian_word || word)) {
        wordText = `，您的词语是：${civilian_word || word}`
    } else if (role === 'god') {
        wordText = '，您可以查看所有角色和词语'
    }

    showNotification('success', `您已被分配为${roleText}角色${wordText}`)
}

// ── 发言 ──────────────────────────────────────────

/**
 * 处理发言轮次
 */
export function handleSpeakingTurn(vm, data) {
    if (vm.speakingTimeout) {
        clearTimeout(vm.speakingTimeout)
        vm.speakingTimeout = null
    }

    vm.currentSpeakerId = data.speaker_id || ''
    vm.speakTimeoutSeconds = data.time_limit || 0

    const isCurrentUserTurn = vm.currentSpeakerId === vm.currentUser?.id
    vm.canSpeak = isCurrentUserTurn

    if (isCurrentUserTurn && vm.$refs.chatInputRef) {
        try { vm.$refs.chatInputRef.focusInput() } catch (_) { /* ignore */ }

        if (data.time_limit && data.time_limit > 0) {
            vm.speakingTimeout = setTimeout(() => {
                if (vm.canSpeak && !vm.newMessage.trim()) {
                    vm.newMessage = '我还没想好...'
                    vm.sendMessage()
                }
            }, data.time_limit * 1000)
        }
    }

    if (isCurrentUserTurn) {
        showNotification('info', `轮到您发言${vm.speakTimeoutSeconds > 0 ? `，时间：${vm.speakTimeoutSeconds}秒` : ''}`)
    }
}

/**
 * 处理立即禁言事件
 */
export function handleImmediateDisableSpeaking(vm, event) {
    if (event.detail.userId === vm.currentUser?.id && vm.canSpeak) {
        vm.canSpeak = false
        vm.currentSpeakerId = ''
        if (vm.speakingTimeout) {
            clearTimeout(vm.speakingTimeout)
            vm.speakingTimeout = null
        }
    }
}

// ── 投票 ──────────────────────────────────────────

/**
 * 处理投票阶段开始事件
 */
export function handleVotePhaseStart(vm, data) {
    vm.canSpeak = false
    vm.currentSpeakerId = ''

    if (vm.speakingTimeout) {
        clearTimeout(vm.speakingTimeout)
        vm.speakingTimeout = null
    }

    showNotification('info', `投票阶段开始，请选择你认为是卧底的玩家。投票时间：${data.detail?.vote_timeout || 10}秒`)
}

/**
 * 处理当前玩家被淘汰事件
 */
export function handleCurrentPlayerEliminated(vm, event) {
    const { playerId, role } = event.detail
    const roleText = role === 'spy' ? '卧底' : role === 'civilian' ? '平民' : '上帝'
    showNotification('warning', `你已被淘汰！你的身份是：${roleText}`)

    vm.canSpeak = false
    vm.currentSpeakerId = ''
    if (vm.speakingTimeout) {
        clearTimeout(vm.speakingTimeout)
        vm.speakingTimeout = null
    }
}

/**
 * 更新遗言阶段的发言状态
 */
export function updateCanSpeakForLastWords(vm) {
    if (vm.roomStore.canSpeakInLastWords) {
        vm.canSpeak = true
        if (vm.$refs.chatInputRef) {
            try { vm.$refs.chatInputRef.focusInput() } catch (_) { /* ignore */ }
        }
    }
}

// ── 游戏结算 ──────────────────────────────────────

/**
 * 显示游戏结算弹窗
 */
export function showGameResultModal(vm, gameEndData) {
    const currentUserId = vm.currentUser?.id
    const winningRole = gameEndData.winning_role
    const roles = gameEndData.roles || {}
    const currentUserRole = roles[currentUserId] || vm.roomStore.currentRole

    vm.isGameResultWin = (
        (currentUserRole === 'civilian' && winningRole === 'civilian') ||
        (currentUserRole === 'spy' && winningRole === 'spy') ||
        (currentUserRole === 'god')
    )

    vm.gameResultWinningRole = winningRole

    // 构建玩家统计
    const players = []
    const users = vm.roomUsers || []
    for (const user of users) {
        const role = roles[user.id] || 'unknown'
        players.push({
            id: user.id,
            username: user.username || (user.id.startsWith('llm_player_') ? `AI玩家_${user.id.replace('llm_player_', '')}` : '未知'),
            avatar_url: user.avatar_url || '/default_avatar.jpg',
            role,
            isWinner: (role === 'civilian' && winningRole === 'civilian') || (role === 'spy' && winningRole === 'spy'),
            isCurrentUser: user.id === currentUserId,
            eliminated: user.eliminated || false
        })
    }

    vm.gameResultStats = {
        players,
        rounds: gameEndData.rounds || vm.roomStore.currentRound || 0,
        duration: vm.gameStartTimestamp ? Math.floor((Date.now() - vm.gameStartTimestamp) / 1000) : 0,
        civilian_word: gameEndData.civilian_word || vm.roomStore.civilianWord || '',
        spy_word: gameEndData.spy_word || vm.roomStore.spyWord || ''
    }

    vm.showGameResult = true
}

/**
 * 处理游戏结算事件（来自 CustomEvent）
 */
export function handleGameResult(vm, event) {
    const data = event.detail
    vm.roomStore.setGameStatus(false)
    showGameResultModal(vm, data)
}
