import { defineStore } from 'pinia'
import { useRoomStore } from './room' // 假设后续会用到
import { useChatStore } from './chat' // 假设后续会用到
import { useUserStore } from './userStore' // 使用正确的 user store
// import router from '@/router' // 按需导入 router

export const useWebsocketStore = defineStore('websocket', {
  state: () => ({
    // WebSocket 实例
    socket: null,
    // 连接状态 ('disconnected', 'connecting', 'connected')
    connectionStatus: 'disconnected',
    // 是否已成功连接过 (用于区分初始连接和重连)
    isConnected: false,
    // 重连尝试次数
    reconnectAttempts: 0,
    // 心跳定时器 ID
    heartbeatInterval: null,
    // 心跳超时定时器 ID
    heartbeatTimeout: null,
    // 目标房间 ID (用于连接和重连)
    targetRoomId: null,
    connectionTimeout: null, // 新增：用于跟踪连接超时
    baseUrl: (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws'),
  }),
  actions: {
    // 连接 WebSocket
    connect(roomId, token) {
      if (this.connectionStatus === 'connecting' || this.connectionStatus === 'connected') {
        console.log('WebSocket 已连接或正在连接，跳过');
        return;
      }

      // 如果是重连，先确保断开
      if (this.socket) {
        this.disconnect(true); // quiet disconnect
      }

      this.targetRoomId = roomId;
      this.connectionStatus = 'connecting';
      console.log(`[WS] 正在连接房间: ${roomId}`);

      if (!token) {
        console.error('[WS] 未找到用户令牌，无法连接WebSocket');
        this.connectionStatus = 'disconnected';
        // 可能需要通知 UI 显示错误
        // useRoomStore().error = '未找到登录信息，请重新登录';
        // router.push('/login'); // 跳转逻辑最好放在调用处或 userStore
        return;
      }

      const wsUrl = `${this.baseUrl}/ws/${roomId}?token=${token}`;
      console.log(`[WS] 连接 URL: ${wsUrl}`);

      try {
        this.socket = new WebSocket(wsUrl);

        // 清除旧的连接超时定时器 (如果有)
        if (this.connectionTimeout) clearTimeout(this.connectionTimeout);

        // 设置连接超时
        this.connectionTimeout = setTimeout(() => {
          if (this.connectionStatus === 'connecting') {
            console.log('[WS] 连接超时');
            this.handleClose({ code: 4008, reason: 'Connection Timeout' }); // 使用自定义 code
          }
        }, 10000); // 10秒连接超时

        // 绑定事件处理器 (指向 store 的 actions)
        this.socket.onopen = this.handleOpen;
        this.socket.onmessage = this.handleMessage;
        this.socket.onclose = this.handleClose;
        this.socket.onerror = this.handleError;

      } catch (error) {
        console.error('[WS] 建立连接时出错:', error);
        this.connectionStatus = 'disconnected';
        // 可能需要通知 UI
        // useRoomStore().error = '创建WebSocket连接失败';
      }
    },
    // 断开 WebSocket
    disconnect(quiet = false) {
      if (!quiet) {
          console.log('[WS] 请求断开连接...');
      }
      
      // 清除心跳定时器
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
       // 清除连接超时定时器
      if (this.connectionTimeout) {
        clearTimeout(this.connectionTimeout);
        this.connectionTimeout = null;
      }
      
      // 关闭 socket
      if (this.socket) {
        try {
          // 移除事件监听器，防止 handleClose 被意外触发两次
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
      
      // 重置状态
      this.isConnected = false;
      this.connectionStatus = 'disconnected';
      this.targetRoomId = null; // 清除目标房间ID
      if (!quiet) { // 重连失败时不清零
          this.reconnectAttempts = 0;
      }
    },
    // 发送消息
    sendMessage(messageObject) {
      if (this.connectionStatus !== 'connected' || !this.socket) {
        console.error('[WS] 发送失败：连接未建立');
        // 可以选择抛出错误或返回 false
        return false;
      }
      try {
        const messageString = JSON.stringify(messageObject);
        this.socket.send(messageString);
        console.log('[WS] 发送消息:', messageObject);
        return true;
      } catch (error) {
        console.error('[WS] 发送消息失败:', error, messageObject);
        // 触发错误处理或断开连接？
        // this.handleError(error);
        return false;
      }
    },
    // 处理收到的消息 (由事件监听器调用)
    handleMessage(event) {
      try {
        const data = JSON.parse(event.data);
        console.log('[WS] 收到消息:', data);

        if (data.type === 'pong') {
          // 清除心跳超时
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          return;
        }

        // TODO: 根据 data.type 分发给其他 Store
        const roomStore = useRoomStore();
        const chatStore = useChatStore();

        switch (data.type) {
          case 'system':
            // --- Convert system message format ---
            let systemContent = '系统消息'; // Default content
            if (data.event === 'connected') {
              // --- Handle new context --- 
              if (data.context === 'create' && data.room_name) {
                systemContent = `您已创建了"${data.room_name}"房间`;
              } else if (data.context === 'join' && data.room_name) {
                systemContent = `您已加入"${data.room_name}"房间`;
              } else {
                systemContent = '已连接到房间'; // Fallback
              }
              // --- End handle new context ---
            } else if (data.message) {
              systemContent = data.message;
            } else if (data.content) {
              systemContent = data.content;
            }
            chatStore.addMessage({
              is_system: true,
              content: systemContent,
              timestamp: data.timestamp || Date.now()
            });
            // --- End conversion ---
            break;
          case 'chat':
            chatStore.addMessage(data);
            break;
          case 'ai_stream':
            // --- Refactor AI Stream Handling ---
            const chatStoreForAI = useChatStore();
            const sessionId = data.session_id;

            if (!sessionId) {
              console.error('[WS] AI stream message missing session_id:', data);
              break; // Cannot process without session ID
            }

            // Find the existing message for this session
            let aiMessage = chatStoreForAI.messages.find(msg => msg.sessionId === sessionId && msg.type === 'ai_stream');

            if (data.is_start) {
              if (!aiMessage) {
                // Create new message only if it doesn't exist
                aiMessage = {
                  // Use session_id also as message id for simplicity if needed
                  id: sessionId, 
                  type: 'ai_stream',
                  content: data.content || '',
                  isStreaming: true,
                  timestamp: data.timestamp || Date.now(),
                  sessionId: sessionId,
                  // Add username and avatar if available in start message (optional)
                  username: 'AI助理', 
                  avatar_url: '/default_room_robot_avatar.jpg' 
                };
                chatStoreForAI.addMessage(aiMessage);
                console.log('[WS] Started new AI stream message:', sessionId);
              } else {
                 // Already exists? Log warning or ignore start flag
                 console.warn('[WS] Received AI stream start flag for existing session:', sessionId);
                 if (data.content) aiMessage.content += data.content; // Still append content if any
                 aiMessage.isStreaming = true; // Ensure streaming is on
              }
            } else if (aiMessage) {
              // Append content to existing message
              if (data.content) {
                aiMessage.content += data.content;
              }
              // Update streaming status based on end flag
              if (data.is_end) {
                aiMessage.isStreaming = false;
                console.log('[WS] Ended AI stream message:', sessionId);
              } else {
                 aiMessage.isStreaming = true; // Ensure it stays true if not ended
              }
            } else {
              // Received a chunk for a session that doesn't exist in store? Log error.
              console.error('[WS] Received AI stream chunk for non-existent session:', sessionId, data);
              // Optionally, create a new message here as a fallback, though ideally backend should send is_start first.
            }
            // --- End Refactor ---
            break;
          case 'secret':
            chatStore.addSecretMessage(data);
            break;
          case 'user_join':
          case 'user_leave':
            if (data.user_list) {
              roomStore.updateUserList(data.user_list);
            }
            if (data.content || data.message) { // 也作为系统消息显示
                chatStore.addMessage({ 
                    is_system: true, 
                    content: data.content || data.message, 
                    timestamp: data.timestamp || Date.now() 
                });
            }
            break;
          case 'ready_status':
            roomStore.updateReadyStatus(data);
            break;
          case 'game_start':
            roomStore.setGameStatus(true);
             chatStore.addMessage({ is_system: true, content: '游戏已开始', timestamp: data.timestamp || Date.now() });
            break;
          case 'game_end':
            roomStore.setGameStatus(false);
            chatStore.addMessage({ is_system: true, content: '游戏已结束', timestamp: data.timestamp || Date.now() });
            break;
          case 'host_leave': 
            if (data.new_host_id) {
              roomStore.setHost(data.new_host_id);
            }
            if (data.user_list) {
              roomStore.updateUserList(data.user_list); 
            }
            if (data.content || data.message) { 
                chatStore.addMessage({ 
                    is_system: true, 
                    content: data.content || data.message, 
                    timestamp: data.timestamp || Date.now() 
                });
            }
            break;
          case 'error':
            roomStore.setError(data.content || data.message || '发生错误');
            console.error('[WS] 收到错误消息:', data.content || data.message);
            break;
          default:
            console.warn('[WS] 未知消息类型:', data.type, data);
            // 可以考虑将未知消息也放入 chatStore 以供调试
            // chatStore.addMessage({ is_system: true, content: `未知消息: ${JSON.stringify(data)}` });
        }

      } catch (error) {
        console.error('[WS] 解析消息失败:', error, event.data);
      }
    },
    // 启动心跳
    startHeartbeat() {
      if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
      if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout);
      this.heartbeatInterval = null;
      this.heartbeatTimeout = null;
      
      this.sendHeartbeat(); // 立即发送一次
      
      this.heartbeatInterval = setInterval(() => {
        this.sendHeartbeat();
      }, 30000); // 30秒
    },
    // 发送具体的心跳消息
    sendHeartbeat() {
      if (this.connectionStatus !== 'connected' || !this.socket) return;

      const pingMessage = {
        type: 'ping',
        timestamp: Date.now()
      };
      
      if (this.sendMessage(pingMessage)) { // 使用封装的 sendMessage
        console.log('[WS] 发送心跳');
        // 设置心跳超时检测 (Pong 必须在 20 秒内返回)
        if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = setTimeout(() => {
          console.log('[WS] 心跳超时 (等待Pong超时)');
          this.handleClose({ code: 4009, reason: 'Heartbeat Timeout' }); // 触发关闭和重连
        }, 20000); // 20秒等待 Pong
      } else {
          console.error('[WS] 发送心跳失败，可能连接已断开');
          // 如果发送失败，也尝试关闭并重连
           this.handleClose({ code: 4010, reason: 'Heartbeat Send Failed' });
      }
    },
    // 处理 WebSocket 关闭事件
    handleClose(event) {
      console.log('[WS] 连接已关闭', event);
      if (this.connectionTimeout) clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;
      
      const previousStatus = this.connectionStatus;
      const wasConnected = this.isConnected;
      
      // 清理定时器和状态 (在 disconnect 中也做，这里确保覆盖)
      if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
      if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout);
      this.heartbeatInterval = null;
      this.heartbeatTimeout = null;
      this.socket = null;
      this.isConnected = false;
      this.connectionStatus = 'disconnected';
      
      // --- Fix handleClose logic ---
      const unexpectedClose = event.code !== 1000 && event.code !== 1001;
      const shouldTryReconnect = (wasConnected || previousStatus === 'connecting');
      const MAX_RECONNECT_ATTEMPTS = 3;

      // 检查是否应该重连 (是意外关闭 & 之前在连接中或已连接 & 未超次 & 知道目标房间)
      if (unexpectedClose && shouldTryReconnect && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS && this.targetRoomId) {
          this.reconnectAttempts++;
          const delay = Math.pow(2, this.reconnectAttempts -1) * 1000 + 1000; // 指数退避 + 1秒基础
          console.log(`[WS] 连接断开 (Code: ${event.code}, Reason: ${event.reason || 'N/A'}), ${delay / 1000}秒后尝试重连 (${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);

          setTimeout(() => {
              console.log(`[WS] 正在执行重连尝试 #${this.reconnectAttempts}`);
              // --- 修复：重新获取 Token --- 
              const userStore = useUserStore(); 
              const currentToken = userStore.accessToken; 
              
              if (this.targetRoomId && currentToken) {
                  console.log(`[WS] 重连时获取到 Token: ${currentToken.substring(0,10)}...`);
                  this.connect(this.targetRoomId, currentToken); // <--- 使用当前 token 重连
              } else {
                  console.error(`[WS] 重连失败：无法获取房间ID (${this.targetRoomId}) 或用户Token (${!!currentToken})`);
                  this.reconnectAttempts = 0; // 重置尝试次数
                  // 可能需要通知用户
                  // useRoomStore().setError('重连服务器失败，请检查登录状态');
              }
          }, delay);
      } else {
          if (unexpectedClose && shouldTryReconnect) {
               console.log(`[WS] 关闭代码: ${event.code}. 达到最大重连次数或目标房间丢失，停止重连.`);
               // useRoomStore().setError('无法重新连接到服务器，请刷新页面');
          } else {
               console.log(`[WS] 连接正常关闭 (Code: ${event.code}) 或无需重连.`);
          }
          this.targetRoomId = null; // 停止重连或正常关闭后清除目标 ID
          this.reconnectAttempts = 0; // 重置尝试次数
      }
      // --- End of fix ---
    },
    // 处理 WebSocket 错误事件
    handleError(error) {
      console.error('[WS] 连接错误:', error);
      // 标记状态，让 handleClose 处理后续逻辑（如重连）
      this.connectionStatus = 'disconnected'; 
      // 通常 onerror 后会触发 onclose，所以在 onclose 中处理重连更可靠
    },
    // --- Add handleOpen method ---
    handleOpen() {
      console.log('[WS] 连接已打开');
      // 清除连接超时定时器
      if (this.connectionTimeout) {
          clearTimeout(this.connectionTimeout);
          this.connectionTimeout = null;
          console.log('[WS] 连接超时定时器已清除');
      }
      // 更新状态
      this.connectionStatus = 'connected';
      this.isConnected = true;
      this.reconnectAttempts = 0; // 连接成功，重置重连次数
      // 启动心跳
      this.startHeartbeat();
    },
    // ---------------------------
  },
}) 