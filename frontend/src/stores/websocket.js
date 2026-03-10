import { defineStore } from 'pinia'
import { useRoomStore } from './room'
import { useChatStore } from './chat'
import { useUserStore } from './userStore'
import { handleOtherMessage } from './wsMessageHandlers'
import { processAiStreamMessage, simulateAiStream } from './wsAiStreamHandler'

export const useWebsocketStore = defineStore('websocket', {
  state: () => ({
    socket: null,
    connectionStatus: 'disconnected',
    isConnected: false,
    reconnectAttempts: 0,
    heartbeatInterval: null,
    heartbeatTimeout: null,
    targetRoomId: null,
    connectionTimeout: null,
    baseUrl: (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws'),
    // 保存当前正在处理的AI会话
    activeAiSessions: new Map(),
  }),
  actions: {
    // ── 连接管理 ──────────────────────────────────────
    connect(roomId, token) {
      if (this.connectionStatus === 'connecting' || this.connectionStatus === 'connected') {
        console.log('WebSocket 已连接或正在连接，跳过');
        return;
      }

      if (this.socket) {
        this.disconnect(true);
      }

      this.targetRoomId = roomId;
      this.connectionStatus = 'connecting';
      console.log(`[WS] 正在连接房间: ${roomId}`);

      if (!token) {
        console.error('[WS] 未找到用户令牌，无法连接WebSocket');
        this.connectionStatus = 'disconnected';
        return;
      }

      const wsUrl = `${this.baseUrl}/ws/${roomId}?token=${token}`;
      console.log(`[WS] 连接 URL: ${wsUrl}`);

      try {
        this.socket = new WebSocket(wsUrl);

        if (this.connectionTimeout) clearTimeout(this.connectionTimeout);

        this.connectionTimeout = setTimeout(() => {
          if (this.connectionStatus === 'connecting') {
            console.log('[WS] 连接超时');
            this.handleClose({ code: 4008, reason: 'Connection Timeout' });
          }
        }, 10000);

        this.socket.onopen = this.handleOpen;
        this.socket.onmessage = this.handleMessage;
        this.socket.onclose = this.handleClose;
        this.socket.onerror = this.handleError;

      } catch (error) {
        console.error('[WS] 建立连接时出错:', error);
        this.connectionStatus = 'disconnected';
      }
    },

    disconnect(quiet = false) {
      if (!quiet) {
        console.log('[WS] 请求断开连接...');
      }

      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      if (this.connectionTimeout) {
        clearTimeout(this.connectionTimeout);
        this.connectionTimeout = null;
      }

      // 清理所有活跃的AI会话定时器
      this.activeAiSessions.forEach(session => {
        if (session.updateTimer) {
          clearTimeout(session.updateTimer);
        }
      });
      this.activeAiSessions.clear();

      if (this.socket) {
        try {
          this.socket.onopen = null;
          this.socket.onmessage = null;
          this.socket.onclose = null;
          this.socket.onerror = null;
          this.socket.close();
        } catch (e) {
          if (!quiet) console.log('[WS] 关闭旧连接时出错:', e);
        }
        this.socket = null;
      }

      this.isConnected = false;
      this.connectionStatus = 'disconnected';
      this.targetRoomId = null;
      if (!quiet) {
        this.reconnectAttempts = 0;
      }
    },

    // ── 消息发送 ──────────────────────────────────────
    sendMessage(messageObject) {
      console.log('[WS] 尝试发送消息:', messageObject);

      if (!this.socket) {
        console.error('[WS] 发送失败：WebSocket对象不存在');
        return false;
      }

      if (this.connectionStatus !== 'connected') {
        console.error('[WS] 发送失败：连接状态异常，当前状态:', this.connectionStatus);
        return false;
      }

      if (this.socket.readyState !== WebSocket.OPEN) {
        console.error('[WS] 发送失败：WebSocket未准备好，readyState =', this.socket.readyState);
        return false;
      }

      try {
        const messageString = JSON.stringify(messageObject);
        console.log('[WS] 准备发送JSON消息:', messageString);
        this.socket.send(messageString);
        console.log('[WS] 消息发送成功');
        return true;
      } catch (error) {
        console.error('[WS] 发送消息失败:', error, messageObject);
        return false;
      }
    },

    // ── 消息接收与分发 ────────────────────────────────
    handleMessage(event) {
      try {
        const data = JSON.parse(event.data);

        // pong 心跳特殊处理
        if (data.type === 'pong') {
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          return;
        }

        console.log('[WS] 收到消息:', data);

        // 遗言消息
        if (data.type === 'last_words') {
          console.log('[WS] 处理遗言消息:', data);
          if (!data.timestamp) data.timestamp = Date.now();

          const isAiPlayer = data.user_id && data.user_id.startsWith('llm_player_');
          if (isAiPlayer) {
            simulateAiStream(data, this.activeAiSessions);
          } else {
            data._priority = true;
            data.type = 'last_words';
            useChatStore().addMessage(data);
          }
          return;
        }

        // 普通聊天消息
        if (data.type === 'chat') {
          if (!data.timestamp) data.timestamp = Date.now();

          const isAiPlayer = data.user_id && data.user_id.startsWith('llm_player_');
          if (isAiPlayer && data.type !== 'last_words') {
            simulateAiStream(data, this.activeAiSessions);
          } else {
            data._priority = true;
            useChatStore().addMessage(data);
          }
        }
        // 非聊天消息 → 异步处理，避免阻塞 UI
        else {
          setTimeout(() => {
            if (data.type === 'ai_stream') {
              processAiStreamMessage(data, this.activeAiSessions);
            } else {
              // 传递 wsActions 回调
              handleOtherMessage(data, {
                triggerCountdownStart: this.triggerCountdownStart.bind(this),
                triggerCountdownCancel: this.triggerCountdownCancel.bind(this)
              });
            }
          }, 0);
        }
      } catch (error) {
        console.error('[WS] 处理消息时出错:', error, event.data);
      }
    },

    // ── 心跳 ─────────────────────────────────────────
    startHeartbeat() {
      if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
      if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout);
      this.heartbeatInterval = null;
      this.heartbeatTimeout = null;

      this.sendHeartbeat();

      this.heartbeatInterval = setInterval(() => {
        this.sendHeartbeat();
      }, 30000);
    },

    sendHeartbeat() {
      if (this.connectionStatus !== 'connected' || !this.socket) return;

      const pingMessage = {
        type: 'ping',
        timestamp: Date.now()
      };

      if (this.sendMessage(pingMessage)) {
        console.log('[WS] 发送心跳');
        if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = setTimeout(() => {
          console.log('[WS] 心跳超时 (等待Pong超时)');
          this.handleClose({ code: 4009, reason: 'Heartbeat Timeout' });
        }, 20000);
      } else {
        console.error('[WS] 发送心跳失败，可能连接已断开');
        this.handleClose({ code: 4010, reason: 'Heartbeat Send Failed' });
      }
    },

    // ── 连接事件 ─────────────────────────────────────
    handleClose(event) {
      console.log('[WS] 连接已关闭', event);
      if (this.connectionTimeout) clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;

      const previousStatus = this.connectionStatus;
      const wasConnected = this.isConnected;

      if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
      if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout);
      this.heartbeatInterval = null;
      this.heartbeatTimeout = null;

      // 清理AI会话
      this.activeAiSessions.forEach(session => {
        if (session.updateTimer) {
          clearTimeout(session.updateTimer);
        }
      });
      this.activeAiSessions.clear();

      this.socket = null;
      this.isConnected = false;
      this.connectionStatus = 'disconnected';

      // 房间已关闭
      if (event.reason === "房间已关闭") {
        console.log('[WS] 检测到房间已关闭');
        const roomStore = useRoomStore();
        const chatStore = useChatStore();
        const userStore = useUserStore();

        const currentUserId = userStore.user?.id;
        const hostId = roomStore.roomInfo?.host_id;
        const isCurrentUserHost = currentUserId === hostId;

        chatStore.clearMessages();
        roomStore.clearRoomState();

        if (!isCurrentUserHost) {
          console.log('[WS] 非房主用户收到房间解散通知');
          alert('房主已解散房间，您将返回大厅');
          window.location.href = '/lobby';
        }
        return;
      }

      // 重连逻辑
      const unexpectedClose = event.code !== 1000 && event.code !== 1001;
      const shouldTryReconnect = (wasConnected || previousStatus === 'connecting');
      const MAX_RECONNECT_ATTEMPTS = 3;

      if (unexpectedClose && shouldTryReconnect && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS && this.targetRoomId) {
        this.reconnectAttempts++;
        const delay = Math.pow(2, this.reconnectAttempts - 1) * 1000 + 1000;
        console.log(`[WS] ${delay / 1000}秒后尝试重连 (${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);

        setTimeout(() => {
          const userStore = useUserStore();
          const currentToken = userStore.accessToken;

          if (this.targetRoomId && currentToken) {
            this.connect(this.targetRoomId, currentToken);
          } else {
            console.error('[WS] 重连失败：无法获取房间ID或Token');
            this.reconnectAttempts = 0;
          }
        }, delay);
      } else {
        this.targetRoomId = null;
        this.reconnectAttempts = 0;
      }
    },

    handleError(error) {
      console.error('[WS] 连接错误:', error);
      this.connectionStatus = 'disconnected';
    },

    handleOpen() {
      console.log('[WS] 连接已打开');
      if (this.connectionTimeout) {
        clearTimeout(this.connectionTimeout);
        this.connectionTimeout = null;
      }
      this.connectionStatus = 'connected';
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    },

    // ── 倒计时 UI 辅助 ──────────────────────────────
    triggerCountdownStart(duration) {
      const roomViewInstance = document.querySelector('.room-container')?.__vueParentComponent?.ctx;
      if (roomViewInstance && roomViewInstance.$refs.countdownOverlay) {
        roomViewInstance.$refs.countdownOverlay.startCountdown(duration);
      }
    },

    triggerCountdownCancel(reason) {
      console.log('[WS] 触发倒计时取消:', reason);

      try {
        const roomViewInstance = document.querySelector('.room-container')?.__vueParentComponent?.ctx;
        if (roomViewInstance && roomViewInstance.$refs.countdownOverlay) {
          roomViewInstance.$refs.countdownOverlay.cancelCountdown();
        } else {
          const overlays = document.querySelectorAll('.countdown-overlay');
          if (overlays.length > 0) {
            overlays.forEach(overlay => { overlay.style.display = 'none'; });
          }
        }
      } catch (error) {
        console.error('[WS] 取消倒计时时出错:', error);
      }

      const chatStore = useChatStore();
      chatStore.addMessage({
        is_system: true,
        content: `倒计时已取消: ${reason}`,
        timestamp: Date.now()
      });
    },

    // ── 辅助方法 ─────────────────────────────────────
    isLastWordsPhase() {
      const roomStore = useRoomStore();
      return roomStore.gamePhase === 'last_words';
    },
  },
}) 