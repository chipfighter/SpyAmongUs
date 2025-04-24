import { defineStore } from 'pinia'
import { useRoomStore } from './room'
import { useChatStore } from './chat'
import { useUserStore } from './userStore'

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
    sendMessage(messageObject) {
      if (this.connectionStatus !== 'connected' || !this.socket) {
        console.error('[WS] 发送失败：连接未建立');
        return false;
      }
      try {
        const messageString = JSON.stringify(messageObject);
        this.socket.send(messageString);
        console.log('[WS] 发送消息:', messageObject);
        return true;
      } catch (error) {
        console.error('[WS] 发送消息失败:', error, messageObject);
        return false;
      }
    },
    handleMessage(event) {
      try {
        const data = JSON.parse(event.data);

        // 对pong消息特殊处理，减少日志
        if (data.type === 'pong') {
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          return;
        }

        console.log('[WS] 收到消息:', data);
        
        // 快速处理普通聊天消息 - 高优先级立即显示
        if (data.type === 'chat') {
          const chatStore = useChatStore();
          // 添加时间戳以确保消息排序正确
          if (!data.timestamp) {
            data.timestamp = Date.now();
          }
          // 为普通消息添加高优先级标记，确保即使在AI流式响应期间也能立即显示
          data._priority = true;
          chatStore.addMessage(data);
        } 
        // 异步处理AI流式消息和其他消息
        else {
          // 使用setTimeout将AI消息处理放入下一个宏任务，避免阻塞UI
          setTimeout(() => {
            this.processNonChatMessage(data);
          }, 0);
        }
      } catch (error) {
        console.error('[WS] 处理消息时出错:', error, event.data);
      }
    },
    
    // 处理非聊天消息
    processNonChatMessage(data) {
      // AI流式消息特殊处理
      if (data.type === 'ai_stream') {
        this.processAiStreamMessage(data);
      } else {
        // 其他类型消息正常处理
        this.processOtherMessage(data);
      }
    },
    
    // 处理AI流式消息
    processAiStreamMessage(data) {
      const sessionId = data.session_id;
      if (!sessionId) {
        console.error('[WS] AI stream message missing session_id:', data);
        return;
      }
      
      const chatStoreForAI = useChatStore();
      
      // 获取或创建会话数据
      let sessionData = this.activeAiSessions.get(sessionId);
      
      // 如果是开始消息，创建新会话
      if (data.is_start) {
        if (!sessionData) {
          sessionData = {
            content: data.content || '',
            updateTimer: null,
            lastUpdateTime: Date.now(),
            needsUpdate: true,
            isStreaming: true,
            timestamp: data.timestamp || Date.now()
          };
          this.activeAiSessions.set(sessionId, sessionData);
          
          // 创建新的AI消息对象
          const aiMessage = {
            id: sessionId, 
            type: 'ai_stream',
            content: sessionData.content,
            isStreaming: true,       // 明确标记为正在流式传输
            is_start: data.is_start, // 保留原始标记
            is_end: data.is_end,     // 保留原始标记
            timestamp: sessionData.timestamp,
            sessionId: sessionId,
            username: 'AI助理', 
            avatar_url: '/default_room_robot_avatar.jpg' 
          };
          
          // 添加消息到聊天存储
          chatStoreForAI.addMessage(aiMessage);
          console.log('[WS] Started new AI stream message:', sessionId);
        } else {
          console.warn('[WS] Received AI stream start flag for existing session:', sessionId);
          if (data.content) {
            sessionData.content += data.content;
            sessionData.needsUpdate = true;
          }
          sessionData.isStreaming = true;
        }
      } 
      // 如果不是开始消息，确保会话存在
      else if (sessionData) {
        // 添加内容
        if (data.content) {
          sessionData.content += data.content;
          sessionData.needsUpdate = true;
        }
        
        // 设置流式状态 - 除非是结束消息，否则一直标记为流式传输中
        sessionData.isStreaming = !data.is_end;
        
        // 检查是否需要立即更新UI
        const shouldUpdateNow = data.is_end || (Date.now() - sessionData.lastUpdateTime > 100);
        
        if (shouldUpdateNow && sessionData.needsUpdate) {
          this.updateAiMessage(sessionId, sessionData);
          sessionData.lastUpdateTime = Date.now();
          sessionData.needsUpdate = false;
        } 
        // 如果不需要立即更新且没有计时器，创建一个
        else if (sessionData.needsUpdate && !sessionData.updateTimer) {
          sessionData.updateTimer = setTimeout(() => {
            if (sessionData.needsUpdate) {
              this.updateAiMessage(sessionId, sessionData);
              sessionData.lastUpdateTime = Date.now();
              sessionData.needsUpdate = false;
            }
            sessionData.updateTimer = null;
          }, 100); // 100ms节流更新
        }
        
        // 如果结束，清理会话
        if (data.is_end) {
          if (sessionData.updateTimer) {
            clearTimeout(sessionData.updateTimer);
          }
          this.activeAiSessions.delete(sessionId);
          console.log('[WS] Ended AI stream message:', sessionId);
        }
      } else {
        console.error('[WS] Received AI stream chunk for non-existent session:', sessionId, data);
      }
    },
    
    // 更新AI消息内容
    updateAiMessage(sessionId, sessionData) {
      const chatStore = useChatStore();
      let aiMessage = chatStore.messages.find(msg => msg.sessionId === sessionId && msg.type === 'ai_stream');
      
      if (aiMessage) {
        aiMessage.content = sessionData.content;
        aiMessage.isStreaming = sessionData.isStreaming; // 更新流式状态
        aiMessage.is_end = !sessionData.isStreaming;     // 同步更新结束标志
        console.log(`[WS] 更新AI消息 ${sessionId}, isStreaming=${aiMessage.isStreaming}`);
      } else {
        console.error('[WS] Cannot find AI message to update:', sessionId);
      }
    },
    
    // 处理其他类型的消息
    processOtherMessage(data) {
        const roomStore = useRoomStore();
        const chatStore = useChatStore();

        switch (data.type) {
          case 'system':
          let systemContent = '系统消息';
            if (data.event === 'connected') {
              if (data.context === 'create' && data.room_name) {
                systemContent = `您已创建了"${data.room_name}"房间`;
              } else if (data.context === 'join' && data.room_name) {
                systemContent = `您已加入"${data.room_name}"房间`;
              } else {
              systemContent = '已连接到房间';
              }
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
            break;
          case 'secret':
            chatStore.addSecretMessage(data);
            break;
        case 'user_list_update':
          roomStore.updateUserList(data.users);
            break;
          case 'user_join':
          case 'user_leave':
        case 'host_leave':
          // 用户加入/离开消息处理
          console.log(`[WS] 收到${data.type === 'user_join' ? '用户加入' : (data.type === 'host_leave' ? '房主离开' : '用户离开')}消息:`, data);
          
          // 根据消息类型处理
          if (data.type === 'user_join') {
            // 用户加入 - 直接使用消息中的字段构建用户对象
            if (data.user_id && data.username) {
              const newUser = {
                id: data.user_id,
                username: data.username,
                avatar_url: data.avatar_url || '/default_avatar.jpg',
                status: 'in_room'
              };
              roomStore.addUser(newUser);
              console.log(`[WS] 添加新用户到列表: ${data.username}`);
            }
          } 
          else if (data.type === 'user_leave') {
            // 普通用户离开 - 根据用户ID移除
            if (data.user_id) {
              roomStore.removeUser(data.user_id);
              console.log(`[WS] 从列表移除用户: ${data.user_id}`);
            }
          }
          else if (data.type === 'host_leave') {
            // 房主离开 - 移除旧房主并设置新房主
            if (data.user_id) {
              roomStore.removeUser(data.user_id);
              if (data.new_host_id) {
                roomStore.setHost(data.new_host_id);
                console.log(`[WS] 房主变更为: ${data.new_host_id}`);
              }
            }
          }
          
          // 添加系统消息通知
          if (data.content) {
                chatStore.addMessage({ 
                    is_system: true, 
              content: data.content,
                    timestamp: data.timestamp || Date.now() 
                });
            }
            break;
        case 'user_ready':
          roomStore.updateReadyStatus(data);
          break;
        case 'user_ready_update': 
            roomStore.updateReadyStatus(data);
            break;
          case 'game_start':
            roomStore.setGameStatus(true);
          // 可能需要导航到游戏界面或更新UI
          console.log('[WS] Game started!');
            break;
        case 'game_over':
            roomStore.setGameStatus(false);
          // 显示游戏结果?
          console.log('[WS] Game over!');
            break;
        case 'countdown_start':
            // 处理倒计时开始消息
            console.log('[WS] 倒计时开始:', data);
            this.triggerCountdownStart(data.duration || 5);
            break;
        case 'countdown_cancelled':
            // 处理倒计时取消消息
            console.log('[WS] 倒计时取消:', data);
            this.triggerCountdownCancel(data.reason || '倒计时已取消');
            break;
        case 'new_host':
            if (data.new_host_id) {
              roomStore.setHost(data.new_host_id);
            }
            break;
        case 'god_role_inquiry':
            // 开始轮询上帝角色时，设置轮询状态为true
            roomStore.setGodPollingStatus(true);
            // 处理上帝角色询问消息
            console.log('[WS] 收到上帝角色询问:', data);
            roomStore.setGodRoleInquiry(true, data.message, data.timeout);
            break;
        case 'god_role_inquiry_status':
            // 收到轮询状态消息时，设置轮询状态为true
            roomStore.setGodPollingStatus(true);
            // 处理上帝角色询问状态广播
            console.log('[WS] 收到上帝角色询问状态:', data);
            roomStore.handleGodRoleInquiryStatus(data);
            break;
        case 'god_role_assigned':
            // 处理上帝角色分配结果
            console.log('[WS] 上帝角色已分配:', data);
            roomStore.setGodRoleInquiry(false);
            if (data.is_ai) {
                roomStore.showToast('info', '没有玩家愿意担任上帝，本局游戏将由AI担任上帝角色');
            } else {
                roomStore.showToast('success', '已选定上帝角色，游戏即将开始');
            }
            break;
        case 'you_are_god':
            // 处理被选为上帝的通知
            console.log('[WS] 您被选为上帝角色');
            roomStore.showToast('success', '您已被选为本局游戏的上帝');
            break;
        case 'god_words_selection':
            // 处理上帝选词消息
            console.log('[WS] 收到上帝选词消息:', data);
            // 通过事件系统将消息传递给组件
            document.dispatchEvent(new CustomEvent('god-words-selection', { 
              detail: data
            }));
            break;
        case 'god_words_selected':
            // 处理选词完成消息，关闭所有状态弹窗
            console.log('[WS] 上帝选词完成:', data);
            
            // 设置游戏状态为加载中
            document.dispatchEvent(new CustomEvent('god-words-selected', { 
              detail: data
            }));
            break;
        case 'role_word_assignment':
            // 处理角色和词语分配消息
            console.log('[WS] 收到角色和词语分配消息:', data);
            // 设置角色信息
            roomStore.setRoleInfo(data);
            break;
        case 'game_initialized':
            // 游戏初始化完成
            console.log('[WS] 游戏初始化完成');
            
            // 设置游戏状态为已开始
            roomStore.setGameStatus(true);
            
            // 结束上帝轮询阶段
            roomStore.setGodPollingStatus(false);
            
            // 发送初始化完成事件，由组件处理UI相关逻辑
            document.dispatchEvent(new CustomEvent('game-initialized', { 
              detail: data
            }));
            break;
          default:
          console.warn('[WS] 未处理的消息类型:', data.type);
      }
    },
    
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
          // 如果发送失败，尝试关闭并重连
           this.handleClose({ code: 4010, reason: 'Heartbeat Send Failed' });
      }
    },
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
      
      // 检查是否是"房间已关闭"的情况
      if (event.reason === "房间已关闭") {
        console.log('[WS] 检测到房间已关闭');
        
        // 清理房间相关数据
        const roomStore = useRoomStore();
        const chatStore = useChatStore();
        const userStore = useUserStore();
        
        // 获取当前用户ID和房间主人ID
        const currentUserId = userStore.user?.id;
        const hostId = roomStore.roomInfo?.host_id;
        const isCurrentUserHost = currentUserId === hostId;
        
        // 清理数据
        chatStore.clearMessages();
        roomStore.clearRoomState();
        
        // 只有非房主才显示"房主已解散房间"的提示
        if (!isCurrentUserHost) {
          console.log('[WS] 非房主用户收到房间解散通知，显示提示并跳转');
          alert('房主已解散房间，您将返回大厅');
          window.location.href = '/lobby';
        }
        
        return; // 提前返回，不尝试重连
      }
      
      const unexpectedClose = event.code !== 1000 && event.code !== 1001;
      const shouldTryReconnect = (wasConnected || previousStatus === 'connecting');
      const MAX_RECONNECT_ATTEMPTS = 3;

      if (unexpectedClose && shouldTryReconnect && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS && this.targetRoomId) {
          this.reconnectAttempts++;
          const delay = Math.pow(2, this.reconnectAttempts -1) * 1000 + 1000; // 指数退避 + 1秒基础
          console.log(`[WS] 连接断开 (Code: ${event.code}, Reason: ${event.reason || 'N/A'}), ${delay / 1000}秒后尝试重连 (${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);

          setTimeout(() => {
              console.log(`[WS] 正在执行重连尝试 #${this.reconnectAttempts}`);
              const userStore = useUserStore(); 
              const currentToken = userStore.accessToken; 
              
              if (this.targetRoomId && currentToken) {
                  console.log(`[WS] 重连时获取到 Token: ${currentToken.substring(0,10)}...`);
                  this.connect(this.targetRoomId, currentToken); // 使用当前已有的 token 重连
              } else {
                  console.error(`[WS] 重连失败：无法获取房间ID (${this.targetRoomId}) 或用户Token (${!!currentToken})`);
                  this.reconnectAttempts = 0; // 重置尝试次数
              }
          }, delay);
      } else {
          if (unexpectedClose && shouldTryReconnect) {
               console.log(`[WS] 关闭代码: ${event.code}. 达到最大重连次数或目标房间丢失，停止重连.`);
          } else {
               console.log(`[WS] 连接正常关闭 (Code: ${event.code}) 或无需重连.`);
          }
          this.targetRoomId = null; // 停止重连或正常关闭后清除目标 ID
          this.reconnectAttempts = 0; // 重置尝试次数
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
          console.log('[WS] 连接超时定时器已清除');
      }
      this.connectionStatus = 'connected';
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    },
    triggerCountdownStart(duration) {
      // 找到所有引用此store的组件中的countdownOverlay引用
      const roomViewInstance = document.querySelector('.room-container')?.__vueParentComponent?.ctx;
      if (roomViewInstance && roomViewInstance.$refs.countdownOverlay) {
        roomViewInstance.$refs.countdownOverlay.startCountdown(duration);
      }
    },
    triggerCountdownCancel(reason) {
      // 找到所有引用此store的组件中的countdownOverlay引用
      const roomViewInstance = document.querySelector('.room-container')?.__vueParentComponent?.ctx;
      if (roomViewInstance && roomViewInstance.$refs.countdownOverlay) {
        roomViewInstance.$refs.countdownOverlay.cancelCountdown();
      }
      
      // 显示取消原因的系统消息
      const chatStore = useChatStore();
      chatStore.addMessage({
        is_system: true,
        content: `倒计时已取消: ${reason}`,
        timestamp: Date.now()
      });
    }
  },
}) 