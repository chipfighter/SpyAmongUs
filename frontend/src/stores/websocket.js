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
        
        // 显式处理遗言消息
        if (data.type === 'last_words') {
          console.log('[WS] 处理遗言消息:', data);
          const chatStore = useChatStore();
          const roomStore = useRoomStore();
          
          // 确保消息包含时间戳
          if (!data.timestamp) {
            data.timestamp = Date.now();
          }
          
          // 识别是否为AI玩家的遗言消息
          const isAiPlayer = data.user_id && data.user_id.startsWith('llm_player_');
          
          if (isAiPlayer) {
            console.log('[WS] 检测到AI玩家遗言消息，转换为流式处理');
            // 将AI遗言消息转换为流式消息
            const sessionId = `ai_lastwords_${Date.now()}`;
            
            // 从遗言消息中提取信息
            const aiPlayerInfo = this.getAiPlayerInfo(data.user_id);
            
            // 创建模拟流式消息会话
            const sessionData = {
              content: data.content || '',
              updateTimer: null,
              lastUpdateTime: Date.now(),
              needsUpdate: true,
              isStreaming: true,
              timestamp: data.timestamp
            };
            this.activeAiSessions.set(sessionId, sessionData);
            
            // 添加AI流式消息
            chatStore.addMessage({
              id: sessionId,
              type: 'ai_stream',
              username: data.username || aiPlayerInfo.username,
              user_id: data.user_id,
              timestamp: sessionData.timestamp,
              content: '',  // 初始为空，模拟流式加载
              isStreaming: true,
              avatarUrl: data.avatar_url || aiPlayerInfo.avatarUrl
            });
            
            // 设置定时器模拟流式输出
            let currentIndex = 0;
            const content = data.content;
            const chunkSize = Math.max(3, Math.floor(content.length / 10)); // 分成约10个片段
            
            sessionData.updateTimer = setInterval(() => {
              if (currentIndex < content.length) {
                const nextIndex = Math.min(currentIndex + chunkSize, content.length);
                const chunk = content.substring(currentIndex, nextIndex);
                sessionData.content += chunk;
                currentIndex = nextIndex;
                
                chatStore.updateAiStreamMessage(sessionId, {
                  content: sessionData.content,
                  isStreaming: true
                });
                
                // 如果已经完成
                if (currentIndex >= content.length) {
                  // 标记流式传输结束
                  sessionData.isStreaming = false;
                  
                  // 最后一次更新
                  chatStore.updateAiStreamMessage(sessionId, {
                    content: sessionData.content,
                    isStreaming: false
                  });
                  
                  // 清除定时器
                  clearInterval(sessionData.updateTimer);
                  sessionData.updateTimer = null;
                  
                  // 移除会话
                  setTimeout(() => {
                    this.activeAiSessions.delete(sessionId);
                  }, 1000);
                }
              }
            }, 100); // 每100ms更新一次
          } else {
            // 添加高优先级标记，确保即使在AI流式响应期间也能立即显示
            data._priority = true;
            
            // 确保消息显示为遗言类型
            data.type = 'last_words';
            
            // 添加遗言消息到聊天
            chatStore.addMessage(data);
          }
          return;
        }
        
        // 快速处理普通聊天消息 - 高优先级立即显示        
        if (data.type === 'chat') {
          const chatStore = useChatStore();
          // 添加时间戳以确保消息排序正确
          if (!data.timestamp) {
            data.timestamp = Date.now();
          }
          
          // 识别是否为AI玩家的消息（包括普通消息和遗言）
          const isAiPlayer = data.user_id && data.user_id.startsWith('llm_player_');
          
          // 修改后的判断，确保不干扰遗言消息
          if (isAiPlayer && data.type !== 'last_words') {
            console.log('[WS] 检测到AI玩家普通消息，转换为流式处理');
            // 将普通AI消息转换为流式消息
            const sessionId = `ai_message_${Date.now()}`;
            
            // 从普通消息中提取信息
            const aiPlayerInfo = this.getAiPlayerInfo(data.user_id);
            
            // 创建模拟流式消息会话
            const sessionData = {
              content: data.content || '',
              updateTimer: null,
              lastUpdateTime: Date.now(),
              needsUpdate: true,
              isStreaming: true,
              timestamp: data.timestamp
            };
            this.activeAiSessions.set(sessionId, sessionData);
            
            // 添加AI流式消息
            chatStore.addMessage({
              id: sessionId,
              type: 'ai_stream',
              username: data.username || aiPlayerInfo.username,
              user_id: data.user_id,
              timestamp: sessionData.timestamp,
              content: '',  // 初始为空，模拟流式加载
              isStreaming: true,
              avatarUrl: data.avatar_url || aiPlayerInfo.avatarUrl
            });
            
            // 设置定时器模拟流式输出
            let currentIndex = 0;
            const content = data.content;
            const chunkSize = Math.max(3, Math.floor(content.length / 10)); // 分成约10个片段
            
            sessionData.updateTimer = setInterval(() => {
              if (currentIndex < content.length) {
                const nextIndex = Math.min(currentIndex + chunkSize, content.length);
                const chunk = content.substring(currentIndex, nextIndex);
                sessionData.content += chunk;
                currentIndex = nextIndex;
                
                chatStore.updateAiStreamMessage(sessionId, {
                  content: sessionData.content,
                  isStreaming: true
                });
                
                // 如果已经完成
                if (currentIndex >= content.length) {
                  // 标记流式传输结束
                  sessionData.isStreaming = false;
                  
                  // 最后一次更新
                  chatStore.updateAiStreamMessage(sessionId, {
                    content: sessionData.content,
                    isStreaming: false
                  });
                  
                  // 清除定时器
                  clearInterval(sessionData.updateTimer);
                  sessionData.updateTimer = null;
                  
                  // 移除会话
                  setTimeout(() => {
                    this.activeAiSessions.delete(sessionId);
                  }, 1000);
                }
              }
            }, 100); // 每100ms更新一次
          } else {
            // 为普通消息添加高优先级标记，确保即使在AI流式响应期间也能立即显示
            data._priority = true;
            
            // 添加调试日志，特别是对于last_words类型
            if (data.type === 'last_words') {
              console.log('[WS] 接收到遗言消息，直接显示:', data);
            }
            
            chatStore.addMessage(data);
          }
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
      const roomStore = useRoomStore();
      
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
          
          // 处理AI玩家名称 - 检查消息是否来自AI玩家
          let username = 'AI助理';
          let avatarUrl = '/default_room_robot_avatar.jpg';
          
          // 如果消息包含AI玩家ID，则使用对应的AI玩家名称
          if (data.user_id && data.user_id.startsWith('llm_player_')) {
            const aiNumber = data.user_id.replace('llm_player_', '');
            username = `AI玩家_${aiNumber}`;
            
            // 从房间store获取更多信息 - 首先查找用户列表
            const aiPlayer = roomStore.users.find(u => u.id === data.user_id);
            if (aiPlayer) {
              username = aiPlayer.username || username;
              avatarUrl = aiPlayer.avatar_url || avatarUrl;
              console.log(`[WS] 从users列表找到AI玩家 ${data.user_id} 的头像: ${avatarUrl}`);
            } else {
              console.log(`[WS] 未在用户列表中找到AI玩家 ${data.user_id}`);
            }
            
            // 检查Redis中分配的AI头像信息
            if (roomStore.roomInfo && roomStore.roomInfo.invite_code) {
              // 这里可以直接从Redis获取AI头像信息
              // 实际上在角色分配时，backend已经发送了ai_avatars信息给前端
              const aiAvatarFromRedisSetting = roomStore.getAiAvatarById(data.user_id);
              if (aiAvatarFromRedisSetting) {
                avatarUrl = aiAvatarFromRedisSetting;
                console.log(`[WS] 从Redis设置中获取AI玩家 ${data.user_id} 的头像: ${avatarUrl}`);
              }
            }
            
            console.log(`[WS] AI玩家消息: ${username}, ID: ${data.user_id}, 最终头像: ${avatarUrl}`);
          }
          
          // 直接创建流式消息
          chatStoreForAI.addMessage({
            id: sessionId,
            type: 'ai_stream',
            username: username,
            user_id: data.user_id || 'ai_assistant',
            timestamp: sessionData.timestamp,
            content: sessionData.content,
            isStreaming: true,
            avatarUrl: avatarUrl
          });
        } else {
          // 会话已存在，但新的开始消息可能表示重置
          sessionData.content = data.content || '';
          sessionData.isStreaming = true;
          sessionData.needsUpdate = true;
          sessionData.timestamp = data.timestamp || Date.now();
          
          // 更新现有消息
          chatStoreForAI.updateAiStreamMessage(sessionId, {
            content: sessionData.content,
            isStreaming: true
          });
        }
      }
      // 如果是数据更新或结束消息
      else if (sessionData) {
        // 更新内容
        if (data.content !== undefined) {
          sessionData.content += data.content;
          sessionData.needsUpdate = true;
        }
        
        // 如果是结束消息，标记流式传输结束
        if (data.is_end) {
          sessionData.isStreaming = false;
          sessionData.needsUpdate = true;
          
          // 清除定时器
          if (sessionData.updateTimer) {
            clearInterval(sessionData.updateTimer);
            sessionData.updateTimer = null;
          }
          
          console.log(`[WS] AI stream session ended: ${sessionId}`);
          
          // 最后一次更新
          chatStoreForAI.updateAiStreamMessage(sessionId, {
            content: sessionData.content,
            isStreaming: false
          });
          
          // 移除会话
          setTimeout(() => {
            this.activeAiSessions.delete(sessionId);
          }, 1000); // 稍微延迟删除，确保界面已更新
          
          return;
        }
        
        // 定时更新界面（如果没有定时器）
        if (!sessionData.updateTimer) {
          sessionData.updateTimer = setInterval(() => {
            // 只有当内容有变化时才更新
            if (sessionData.needsUpdate) {
              chatStoreForAI.updateAiStreamMessage(sessionId, {
                content: sessionData.content,
                isStreaming: sessionData.isStreaming
              });
              
              sessionData.lastUpdateTime = Date.now();
              sessionData.needsUpdate = false;
            }
          }, 100); // 每100ms更新一次，确保流畅
        }
      } else {
        console.warn(`[WS] Received stream data for unknown session: ${sessionId}`);
      }
    },
    
    // 处理其他类型的消息
    processOtherMessage(data) {
      const chatStore = useChatStore();
      const roomStore = useRoomStore();
      const userStore = useUserStore();

      console.log('[WS] 处理其他类型消息:', data);
      
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
          if (data.users && Array.isArray(data.users)) {
            console.log(`[WS] 收到用户列表更新: ${data.users.length} 名用户`);
            data.users.forEach((user, index) => {
              console.log(`  用户 ${index + 1}: id=${user?.id}, username=${user?.username}`);
            });
            roomStore.updateUserList(data.users);
          } else {
            console.warn('[WS] 收到的用户列表更新消息格式不正确:', data);
          }
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
        case 'game_end':
          // 处理游戏结束消息
          console.log('[WS] 游戏结束:', data);
          
          // 更新房间状态
          roomStore.setGameStatus(false);
          
          // 添加游戏结束系统消息
          const winningRoleName = data.winning_role === 'civilian' ? '平民' : '卧底';
          chatStore.addMessage({
            is_system: true,
            content: `游戏结束，${winningRoleName}阵营获胜！`,
            timestamp: data.timestamp || Date.now()
          });

          // 记录所有玩家角色
          if (data.roles) {
            Object.entries(data.roles).forEach(([playerId, role]) => {
              roomStore.handlePlayerEliminated(playerId, role);
            });
          }
          
          // 触发游戏结算弹窗显示
          document.dispatchEvent(new CustomEvent('game-result', { 
            detail: data
          }));
          
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
        case 'player_voted':
            // 处理玩家投票消息
            console.log('[WS] 收到玩家投票消息:', data);
            
            // 更新投票信息
            if (data.vote_count) {
              roomStore.updateVoteCount(data.vote_count);
            }
            
            // 记录谁投票给谁
            if (data.voter_id && data.target_id) {
              roomStore.recordVote(data.voter_id, data.target_id);
            }
            
            // 系统消息已由后端通过另一条消息发送，不需要在这里添加
            break;
        case 'vote_cast':
            // 处理投票事件消息
            console.log('[WS] 收到投票事件消息:', data);
            
            // 记录谁投票给谁
            if (data.voter_id && data.target_id) {
              roomStore.recordVote(data.voter_id, data.target_id);
              
              // 添加系统消息通知
              chatStore.addMessage({
                is_system: true,
                content: `${data.voter_name || '玩家'} 投票给了 ${data.target_name || '目标玩家'}`,
                timestamp: data.timestamp || Date.now()
              });
              
              // 关键修复：更新投票计数
              if (data.vote_count) {
                console.log('[WS] 更新投票计数数据:', data.vote_count);
                roomStore.updateVoteCount(data.vote_count);
              } else {
                console.warn('[WS] 投票事件消息中缺少vote_count数据，尝试增加目标玩家票数');
                // 尝试手动增加票数
                const voteCount = {...roomStore.voteCount};
                voteCount[data.target_id] = (voteCount[data.target_id] || 0) + 1;
                roomStore.updateVoteCount(voteCount);
              }
            }
            break;
        case 'vote_phase_start':
            // 处理投票阶段开始消息
            console.log('[WS] 投票阶段开始:', data);
            
            // 清除之前的投票记录
            roomStore.clearVotes();
            
            // 注意：不应该直接设置roomStore.currentPhase，而应该调用updateGamePhase方法
            // roomStore.currentPhase = 'voting'; // 错误的方式
            // 更新当前游戏阶段
            roomStore.updateGamePhase('voting');
            console.log('[WS] 通过updateGamePhase设置投票阶段:', roomStore.gamePhase);
            
            // 额外检查游戏状态
            if (!roomStore.gameStarted) {
              roomStore.gameStarted = true;
              console.log('[WS] 确保游戏已开始状态');
            }
            
            // 更新回合数
            if (data.current_round) {
              roomStore.updateGameRound(data.current_round);
            }
            
            // 显示系统消息
            chatStore.addMessage({
              is_system: true,
              content: `投票阶段开始，请选择你怀疑的玩家进行投票。投票时间：${data.vote_timeout || 10}秒`,
              timestamp: data.timestamp || Date.now()
            });
            
            // 派发事件通知组件处理UI更新
            document.dispatchEvent(new CustomEvent('vote-phase-start', { 
              detail: data
            }));
            
            // 检查更新后的状态
            setTimeout(() => {
              console.log('[WS] 投票阶段设置后检查状态:', {
                gamePhase: roomStore.gamePhase,
                gameStarted: roomStore.gameStarted
              });
            }, 100);
            
            break;
        case 'player_eliminated':
            // 处理玩家被淘汰消息
            console.log('[WS] 收到玩家被淘汰消息:', data);
            
            // 标记玩家为已淘汰并揭示角色
            if (data.player_id && data.role) {
                roomStore.handlePlayerEliminated(data.player_id, data.role);
                
                // 如果是当前用户被淘汰，显示特殊提示
                if (userStore.user && data.player_id === userStore.user.id) {
                    roomStore.showToast('warning', '你已被淘汰，但仍可以观看游戏进行');
                    
                    // 触发事件通知组件更新UI
                    document.dispatchEvent(new CustomEvent('current-player-eliminated', {
                        detail: { playerId: data.player_id, role: data.role }
                    }));
                }
                
                // 如果接收到玩家被淘汰消息，应立即更新游戏阶段为last_words（因为后端已进入此阶段）
                if (roomStore.gamePhase === 'voting') {
                    console.log('[WS] 收到玩家淘汰消息，更新游戏阶段为last_words');
                    roomStore.updateGamePhase('last_words');
                }
            }
            
            break;
        case 'role_word_assignment':
            // 处理角色和词语分配消息
            console.log('[WS] 收到角色和词语分配消息:', data);
            
            // 确保角色信息正确传递到roomStore
            if (data.role) {
              // 如果是自己的角色信息，确保设置正确
              console.log('[WS] 设置当前用户角色:', data.role);
              
              // 确保roles对象存在
              if (!data.roles) data.roles = {};
              
              // 获取当前用户ID
              const userStore = useUserStore();
              const currentUserId = userStore.user?.id;
              
              // 将自己的角色添加到roles对象中
              if (currentUserId) {
                data.roles[currentUserId] = data.role;
                console.log('[WS] 将当前用户角色添加到roles对象中:', {
                  userId: currentUserId,
                  role: data.role,
                  roles: data.roles
                });
              }
              
              // 对于普通玩家，确保词语信息正确传递
              if (data.role === 'civilian' && data.word) {
                // 为平民玩家添加civilian_word字段
                data.civilian_word = data.word;
                console.log('[WS] 为平民补充civilian_word字段:', data.civilian_word);
              } else if (data.role === 'spy' && data.word) {
                // 为卧底玩家添加spy_word字段
                data.spy_word = data.word;
                console.log('[WS] 为卧底补充spy_word字段:', data.spy_word);
              }
            }
            
            // 如果消息中含有上帝ID，添加到数据中
            if (data.god_id) {
              console.log('[WS] 收到上帝ID:', data.god_id);
              // 确保roles对象存在
              if (!data.roles) data.roles = {};
              // 设置上帝角色
              data.roles[data.god_id] = 'god';
            }
            
            // 设置角色信息
            roomStore.setRoleInfo(data);
            
            // 确保isGodPolling状态设置为false
            if (roomStore.isGodPolling) {
              console.log('[WS] 角色分配后结束上帝轮询状态');
              roomStore.setGodPollingStatus(false);
            }
            
            // 如果没有特定阶段，默认设置为speaking
            if (!data.current_phase && roomStore.gamePhase === '') {
              console.log('[WS] 角色分配时未指定游戏阶段，默认设置为speaking');
              roomStore.updateGamePhase('speaking');
            }
            
            // 派发事件通知前端组件关闭游戏初始化动画
            document.dispatchEvent(new CustomEvent('role-assigned', { 
              detail: data
            }));
            break;
        case 'game_initialized':
            // 游戏初始化完成
            console.log('[WS] 游戏初始化完成');
            
            // 不重复设置游戏状态，因为已在role_word_assignment消息中设置
            // roomStore.setGameStatus(true);
            
            // 如果有游戏阶段和回合数据，更新到roomStore
            if (data.current_phase) {
              console.log(`[WS] 游戏初始化: 设置游戏阶段为 ${data.current_phase}`);
              roomStore.updateGamePhase(data.current_phase);
              console.log(`[WS] 游戏阶段已更新为: ${roomStore.gamePhase}`);
            } else {
              // 默认设置为speaking阶段
              console.log('[WS] 游戏初始化: 未提供游戏阶段，默认设置为speaking');
              roomStore.updateGamePhase('speaking');
            }
            
            if (data.current_round) {
              console.log(`[WS] 游戏初始化: 设置回合为 ${data.current_round}`);
              roomStore.updateGameRound(data.current_round);
            } else {
              // 默认设置为第1回合
              console.log('[WS] 游戏初始化: 未提供回合数，默认设置为1');
              roomStore.updateGameRound(1);
            }
            
            // 结束上帝轮询阶段 - 非常重要
            console.log('[WS] 游戏初始化完成: 结束上帝轮询状态');
            roomStore.setGodPollingStatus(false);
            
            // 发送初始化完成事件，由组件处理UI相关逻辑
            document.dispatchEvent(new CustomEvent('game-initialized', { 
              detail: data
            }));
            break;
        case 'game_phase_update':
            console.log('[WS] 游戏阶段更新:', data);
            if (data.phase) {
              console.log(`[WS] 正在更新游戏阶段从 ${roomStore.gamePhase} 到 ${data.phase}`);
              roomStore.updateGamePhase(data.phase);
              console.log(`[WS] 游戏阶段已更新为: ${roomStore.gamePhase}`);
            }
            if (data.round) {
              console.log(`[WS] 正在更新游戏回合从 ${roomStore.currentRound} 到 ${data.round}`);
              roomStore.updateGameRound(data.round);
              console.log(`[WS] 游戏回合已更新为: ${roomStore.currentRound}`);
            }
            
            // 确保结束上帝轮询状态
            if (roomStore.isGodPolling) {
              console.log('[WS] 游戏阶段更新后结束上帝轮询状态');
              roomStore.setGodPollingStatus(false);
            }
            break;
        case 'speaking_turn':
            // 广播发言轮次消息，通知前端谁可以发言
            console.log('[WS] 收到发言轮次消息:', data);
            
            // 使用事件系统将消息传递给RoomView组件处理
            document.dispatchEvent(new CustomEvent('speaking-turn', { 
              detail: data
            }));
            
            // 如果有提示消息，显示系统提示
            if (data.message) {
              chatStore.addMessage({
                is_system: true,
                content: data.message,
                timestamp: data.timestamp || Date.now()
              });
            }
            break;
        case 'last_words_start':
            // 处理遗言阶段开始消息
            console.log('[WS] 遗言阶段开始:', data);
            
            // 更新当前游戏阶段
            roomStore.updateGamePhase('last_words');
            
            // 显示系统消息
            chatStore.addMessage({
                is_system: true,
                content: `${data.player_name || '玩家'} 进入遗言阶段，时间：${data.timeout || 10}秒`,
                timestamp: data.timestamp || Date.now()
            });
            
            // 记录当前遗言玩家ID
            roomStore.setLastWordsPlayerId(data.player_id);
            
            // 检查是否是当前用户，如果是则允许发言
            const userStore = useUserStore();
            if (data.player_id === userStore.user?.id) {
                console.log('[WS] 当前用户可以发表遗言');
                roomStore.setCanSpeakInLastWords(true);
            }
            
            // 派发事件通知组件处理UI更新
            document.dispatchEvent(new CustomEvent('last-words-phase-start', {
                 detail: data
            }));
            
            break;
        case 'vote_result':
            // 处理投票结果消息
            console.log('[WS] 投票结果:', data);
            
            // 清除投票状态
            roomStore.clearVotes();
            
            // 显示投票结果消息
            if (data.result === 'tie') {
                chatStore.addMessage({
                    is_system: true,
                    content: data.message || "投票结束，没有玩家被淘汰",
                    timestamp: data.timestamp || Date.now()
                });
                
                // 显示通知
                roomStore.showToast('info', data.message || "投票结束，没有玩家被淘汰");
            }
            
            break;
        case 'last_words_phase_end':
            // 处理遗言阶段结束消息
            console.log('[WS] 遗言阶段结束:', data);
            
            // 避免重复处理遗言阶段结束
            if (roomStore.gamePhase === 'last_words') {
                // 清除遗言相关状态
                roomStore.clearLastWordsState();
                
                // 显示系统消息
                chatStore.addMessage({
                    is_system: true,
                    content: `遗言阶段结束`,
                    timestamp: data.timestamp || Date.now()
                });
            } else {
                console.log('[WS] 忽略重复的遗言阶段结束消息，当前游戏阶段:', roomStore.gamePhase);
            }
            
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
      // 使用更可靠的方式查找CountdownOverlay组件
      console.log('[WS] 触发倒计时取消:', reason);
      
      try {
        // 1: 尝试通过Vue组件树查找
        const roomViewInstance = document.querySelector('.room-container')?.__vueParentComponent?.ctx;
        if (roomViewInstance && roomViewInstance.$refs.countdownOverlay) {
          console.log('[WS] 找到CountdownOverlay引用，调用cancelCountdown');
          roomViewInstance.$refs.countdownOverlay.cancelCountdown();
        } else {
          // 2: 直接通过DOM操作查找所有倒计时覆盖层并隐藏
          console.log('[WS] 未找到CountdownOverlay引用，尝试通过DOM查找');
          const overlays = document.querySelectorAll('.countdown-overlay');
          if (overlays.length > 0) {
            console.log('[WS] 通过DOM找到', overlays.length, '个倒计时覆盖层');
            overlays.forEach(overlay => {
              overlay.style.display = 'none';
            });
          } else {
            console.warn('[WS] 未找到任何倒计时覆盖层元素');
          }
        }
      } catch (error) {
        console.error('[WS] 取消倒计时时出错:', error);
      }
      
      // 显示取消原因的系统消息
      const chatStore = useChatStore();
      chatStore.addMessage({
        is_system: true,
        content: `倒计时已取消: ${reason}`,
        timestamp: Date.now()
      });
    },
    // 辅助方法：检查当前是否处于遗言阶段
    isLastWordsPhase() {
      const roomStore = useRoomStore();
      return roomStore.gamePhase === 'last_words';
    },
    
    // 辅助方法：获取AI玩家信息
    getAiPlayerInfo(userId) {
      const roomStore = useRoomStore();
      
      // 默认信息
      const defaultInfo = {
        username: 'AI玩家',
        avatarUrl: '/default_room_robot_avatar.jpg'
      };
      
      if (!userId || !userId.startsWith('llm_player_')) {
        return defaultInfo;
      }
      
      // 从userId中提取编号
      const aiNumber = userId.replace('llm_player_', '');
      defaultInfo.username = `AI玩家_${aiNumber}`;
      
      // 从roomStore中查找AI玩家
      const aiPlayer = roomStore.users.find(u => u.id === userId);
      if (aiPlayer) {
        return {
          username: aiPlayer.username || defaultInfo.username,
          avatarUrl: aiPlayer.avatar_url || defaultInfo.avatarUrl
        };
      }
      
      // 检查Redis中分配的AI头像信息
      if (roomStore.roomInfo && roomStore.roomInfo.invite_code) {
        const aiAvatarFromRedisSetting = roomStore.getAiAvatarById(userId);
        if (aiAvatarFromRedisSetting) {
          defaultInfo.avatarUrl = aiAvatarFromRedisSetting;
        }
      }
      
      return defaultInfo;
    }
  },
}) 