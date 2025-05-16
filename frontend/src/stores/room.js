import { defineStore } from 'pinia'
import { useUserStore } from './userStore'
import { useWebsocketStore } from './websocket'
import { useChatStore } from './chat'

// 初始状态工厂函数
const getDefaultState = () => ({
  roomInfo: {
    name: null,
    invite_code: null,
    host_id: null,
    status: null,
    total_players: 8,
  },
  users: [],
  readyUsers: [],
  gameStarted: false,
  isCurrentUserReady: false,
  isLoading: false,
  loadingText: '加载中...',
  error: null,
  showSecretChatModal: false,
  isGodPolling: false,
  roles: null,
  currentRole: '',
  spyTeammates: [],
  gamePhase: 'speaking',
  currentRound: 1,
  civilianWord: '',
  spyWord: '',
  // 添加投票相关状态
  voteCount: {},
  votedPlayers: {}, // 记录谁投票给谁
  // 添加遗言相关状态
  lastWordsPlayerId: null,
  canSpeakInLastWords: false,
  previousGamePhase: null,
  // AI头像映射
  aiAvatarMapping: {}
})

export const useRoomStore = defineStore('room', {
  state: getDefaultState,
  actions: {
    // --- API Calls ---
    async fetchRoomDetails(roomId) {
      console.log(`[RoomStore] Fetching room details for ${roomId}`);
      this.isLoading = true;
      this.loadingText = '正在加载房间信息...';
      this.error = null;
      const userStore = useUserStore();
      const chatStore = useChatStore();

      try {
        console.log('[RoomStore] Token being used for fetchRoomDetails:', userStore.accessToken); 
        
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${roomId}`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${userStore.accessToken}`
          }
        });
        const result = await response.json();
        console.log('[RoomStore] API fetch response:', result);

        if (result.success && result.data && result.data.room_data) {
          const roomData = result.data.room_data;
          this.roomInfo = {
            name: roomData.room_name,
            invite_code: roomId,
            host_id: roomData.host_id,
            status: roomData.status,
            total_players: roomData.total_players || 8,
          };
          this.users = roomData.users || [];
          console.log('[RoomStore] State updated after fetch:');
          console.log('[RoomStore] this.roomInfo:', JSON.stringify(this.roomInfo));
          console.log('[RoomStore] this.users:', JSON.stringify(this.users));
          this.isLoading = false;
          return true;
        } else {
          throw new Error(result.message || '获取房间信息失败');
        }
      } catch (error) {
        console.error('[RoomStore] Fetch room details failed:', error);
        this.error = error.message;
        this.isLoading = false;
        return false;
      }
    },
    async leaveRoom() {
        if (!this.roomInfo.invite_code) return false;
        console.log(`[RoomStore] Leaving room ${this.roomInfo.invite_code}`);
        this.isLoading = true;
        this.loadingText = '正在退出房间...';
        this.error = null;
        const userStore = useUserStore();
        const websocketStore = useWebsocketStore();
        const chatStore = useChatStore();

        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${this.roomInfo.invite_code}/leave_room`, {
                method: 'POST',
                headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${userStore.accessToken}`
                }
            });
            const result = await response.json();
            if (result.success) {
                console.log('[RoomStore] Left room successfully');
                websocketStore.disconnect();
                chatStore.clearMessages();
                this.clearRoomState();
                this.isLoading = false;
                return true;
            } else {
                throw new Error(result.message || '退出房间失败');
            }
        } catch (error) {
            console.error('[RoomStore] Leave room failed:', error);
            this.error = error.message;
            this.isLoading = false;
            return false;
        }
    },
    async disbandRoom() {
        const userStoreForCheck = useUserStore();
        const hostId = this.roomInfo?.host_id;
        const currentUserId = userStoreForCheck.user?.id;
        const isHostCheck = hostId === currentUserId;
        console.log(`[RoomStore Pre-Disband Check] Invite Code: ${this.roomInfo?.invite_code}, Host ID: ${hostId}, Current User ID: ${currentUserId}, Is Host: ${isHostCheck}`);

        if (!this.roomInfo?.invite_code || !isHostCheck) { 
            console.warn('[RoomStore Disband] Guard condition failed or user is not host.');
            return false; 
        }

        console.log(`[RoomStore] Disbanding room ${this.roomInfo.invite_code}`);
        this.isLoading = true;
        this.loadingText = '正在解散房间...';
        this.error = null;
        const userStore = useUserStore();
        const websocketStore = useWebsocketStore();
        const chatStore = useChatStore();

        try {
            const apiUrl = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${this.roomInfo.invite_code}/delete_room`;
            const accessToken = userStore.accessToken;

            const response = await fetch(apiUrl, {
                method: 'POST', 
                headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
                }
            });

            const result = await response.json();
             if (result.success) {
                console.log('[RoomStore] Disbanded room successfully');
                websocketStore.disconnect();
                chatStore.clearMessages();
                this.clearRoomState();
                this.isLoading = false;
                return true;
            } else {
                throw new Error(result.message || '解散房间失败');
            }
        } catch (error) {
            console.error('[RoomStore] Disband room failed:', error);
            console.error('[RoomStore] Full error object:', error); 
            this.error = error.message;
            this.isLoading = false;
            return false;
        }
    },

    // --- WebSocket Event Handlers (called by websocketStore) ---
    setRoomInfo(data) {
      console.log('[RoomStore] Setting room info:', data);
      this.roomInfo = { ...this.roomInfo, ...data };
    },
    updateUserList(users) {
      console.log('[RoomStore] Updating user list:', users);
      if (Array.isArray(users)) {
        console.log(`[RoomStore] Received ${users.length} users. Details:`);
        users.forEach((user, index) => {
          console.log(`  User ${index}: id=${user?.id}, username=${user?.username}, avatar_url=${user?.avatar_url}`);
        });
      } else {
        console.warn('[RoomStore] Received non-array data for user list:', users);
      }
      this.users = users || [];
    },
    async updateUserListByIds(userIds) {
      if (!Array.isArray(userIds) || userIds.length === 0) {
        console.warn('[RoomStore] Invalid or empty user IDs received:', userIds);
        return;
      }
      
      console.log(`[RoomStore] Updating user list by IDs: ${userIds.length} users`);
      
      // 如果房间已有用户列表，先尝试用本地数据更新
      const localUpdatedList = [];
      const missingIds = [];
      
      // 首先从现有列表中找匹配的用户
      for (const userId of userIds) {
        const existingUser = this.users.find(u => u.id === userId);
        if (existingUser) {
          localUpdatedList.push(existingUser);
        } else {
          missingIds.push(userId);
        }
      }
      
      // 如果没有缺失的用户ID，直接更新
      if (missingIds.length === 0) {
        console.log('[RoomStore] Updated user list using local data');
        this.users = localUpdatedList;
        return;
      }
      
      // 如果有缺失的用户ID，需要重新获取完整房间信息
      if (this.roomInfo?.invite_code) {
        console.log(`[RoomStore] Fetching room details due to missing user data: ${missingIds.length} unknown users`);
        await this.fetchRoomDetails(this.roomInfo.invite_code);
      } else {
        console.warn('[RoomStore] Cannot fetch missing user info: Missing invite_code');
        // 仍然使用部分更新的列表
        this.users = localUpdatedList;
      }
    },
    setHost(newHostId) {
      console.log(`[RoomStore] Setting new host: ${newHostId}`);
       if (this.roomInfo) {
           this.roomInfo.host_id = newHostId;
       }
    },
    addUser(newUser) {
      // 避免重复添加同一用户
      if (!this.users.some(user => user.id === newUser.id)) {
        this.users = [...this.users, newUser];
        console.log(`[RoomStore] Added user to list: ${newUser.username}`);
      }
    },
    removeUser(userId) {
      const userToRemove = this.users.find(user => user.id === userId);
      if (userToRemove) {
        console.log(`[RoomStore] Removing user from list: ${userToRemove.username}`);
        this.users = this.users.filter(user => user.id !== userId);
      }
    },
    updateReadyStatus(payload) { 
      console.log('[RoomStore] Handling user_ready_update message:', payload);

      // 直接从payload中获取数据，适应后端格式
      let user_id, is_ready;

      // 处理后端发来的标准格式: {type: "user_ready", payload: {user_id: "xxx", is_ready: true/false}}
      if (payload.payload && typeof payload.payload.user_id !== 'undefined' && typeof payload.payload.is_ready !== 'undefined') {
        user_id = payload.payload.user_id;
        is_ready = payload.payload.is_ready;
      } else {
        console.warn('[RoomStore] 无法识别的准备状态更新格式:', payload);
        return;
      }
      
      const userStore = useUserStore();

      // 更新readyUsers集合，不管是当前用户还是其他用户
      const currentReadyUsers = new Set(this.readyUsers);
      if (is_ready) {
          if (!currentReadyUsers.has(user_id)) {
               currentReadyUsers.add(user_id);
               console.log(`[RoomStore] Added ${user_id} to readyUsers Set.`);
          }
      } else {
          if (currentReadyUsers.has(user_id)) {
               currentReadyUsers.delete(user_id);
               console.log(`[RoomStore] Removed ${user_id} from readyUsers Set.`);
          }
      }
      this.readyUsers = Array.from(currentReadyUsers);

      // 仅当是当前用户时才更新isCurrentUserReady状态
      if (user_id === userStore.user?.id) {
          this.isCurrentUserReady = !!is_ready;
          console.log(`[RoomStore] Updated isCurrentUserReady to: ${this.isCurrentUserReady}`);
      }

      console.log('[RoomStore] readyUsers state after update:', JSON.stringify(this.readyUsers));
    },
    setGameStatus(started) {
        console.log(`[RoomStore] Setting game status to: ${started}`);
      this.gameStarted = started;
      if (!started) {
        this.readyUsers = [];
        this.isCurrentUserReady = false;
      }
    },

    // --- Component Actions ---
    async toggleReady() {
      if (!this.roomInfo?.invite_code) {
        console.error('[RoomStore] toggleReady: Missing invite_code');
        this.setError('无法切换准备状态：房间信息不完整');
        return;
      }

      const userStore = useUserStore();
      const inviteCode = this.roomInfo.invite_code;
      const apiUrl = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${inviteCode}/ready`;
      const accessToken = userStore.accessToken;

      if (!accessToken) {
        console.error('[RoomStore] toggleReady: Missing access token');
        this.setError('无法切换准备状态：用户未登录');
        return;
      }

      console.log(`[RoomStore] Calling toggleReady API for room ${inviteCode}`);
      this.setError(null); 

      try {
        const response = await fetch(apiUrl, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
          },
        });

        if (!response.ok) {
          let errorMessage = '切换准备状态失败';
          try {
            const errorResult = await response.json();
            errorMessage = errorResult.detail || errorResult.message || errorMessage;
          } catch (parseError) {
            errorMessage = `请求失败，状态码: ${response.status}`;
          }
          throw new Error(errorMessage);
        }

        // 解析响应结果
        const result = await response.json();
        console.log(`[RoomStore] toggleReady API call successful:`, result);

        // 立即更新本地状态 (WebSocket更新可能有延迟)
        if (result.success && result.data && typeof result.data.is_ready === 'boolean') {
          const myUserId = userStore.user?.id;
          // 更新当前用户的准备状态
          this.isCurrentUserReady = result.data.is_ready;
          
          // 更新readyUsers数组
          const currentReadyUsers = new Set(this.readyUsers);
          if (result.data.is_ready) {
            if (!currentReadyUsers.has(myUserId)) {
              currentReadyUsers.add(myUserId);
            }
          } else {
            if (currentReadyUsers.has(myUserId)) {
              currentReadyUsers.delete(myUserId);
            }
          }
          this.readyUsers = Array.from(currentReadyUsers);
          
          console.log(`[RoomStore] 本地更新准备状态: ${result.data.is_ready}`);
          console.log(`[RoomStore] 当前准备用户: ${JSON.stringify(this.readyUsers)}`);
        }

      } catch (error) {
        console.error('[RoomStore] toggleReady API call failed:', error);
        this.setError(error.message);
      }
    },
    setError(message) {
      console.error('[RoomStore] Error set:', message);
      this.error = message;
    },
    clearError() {
        console.log('[RoomStore] Clearing error');
        this.error = null;
    },
    // --- State Management ---
    clearRoomState() {
      console.log('[RoomStore] 清理房间状态');
      
      // 保存现有用户列表和房间基本信息
      const preserveUsers = [...this.users];
      const preserveRoomInfo = { ...this.roomInfo };
      const preserveReadyUsers = [...this.readyUsers];
      
      // 获取默认状态
      const newState = getDefaultState();
      
      // 重置除了用户和房间基本信息外的所有状态
      for (const key in newState) {
        if (key !== 'users' && key !== 'roomInfo' && key !== 'readyUsers') {
          this[key] = newState[key];
        }
      }
      
      // 恢复用户列表和房间基本信息
      this.users = preserveUsers;
      this.roomInfo = preserveRoomInfo;
      this.readyUsers = preserveReadyUsers;
      
      // 确保所有用户的状态正常（清除淘汰状态、角色信息等）
      this.users = this.users.map(user => ({
        ...user,
        eliminated: false,
        role_revealed: false,
        role: undefined
      }));
      
      console.log('[RoomStore] 房间状态已重置，保留用户列表和房间信息');
    },
    
    // 处理上帝角色询问
    setGodRoleInquiry(visible, message, timeout) {
      console.log(`[RoomStore] 设置上帝角色询问: visible=${visible}, message=${message}, timeout=${timeout}`);
      
      // 直接使用自定义事件触发弹窗显示，移除对$toast的依赖
      if (visible) {
        // 触发RoomView组件中的显示询问弹窗
        document.dispatchEvent(new CustomEvent('god-role-inquiry', { 
          detail: { visible, message, timeout } 
        }));
      } else {
        // 关闭询问弹窗
        document.dispatchEvent(new CustomEvent('god-role-inquiry', { 
          detail: { visible: false } 
        }));
      }
    },
    
    // 处理上帝角色询问状态广播
    handleGodRoleInquiryStatus(data) {
      console.log('[RoomStore] 处理上帝角色询问状态广播:', data);
      
      const userStore = useUserStore();
      const isCurrentUser = userStore.user?.id === data.current_user;
      
      // 如果不是当前用户，则触发事件显示询问状态弹窗
      if (!isCurrentUser) {
        // 显示toast提示
        if (data.message) {
        this.showToast('info', data.message);
        }
        
        // 触发事件显示询问状态弹窗
        document.dispatchEvent(new CustomEvent('god-role-inquiry-status', { 
          detail: { 
            visible: true, 
            message: data.message || '正在询问玩家是否愿意担任上帝...', 
            timeout: data.timeout || 7, 
            username: data.username || '' 
          } 
        }));
      }
    },
    
    // 显示Toast消息
    showToast(type, message) {
      console.log(`[RoomStore] 显示Toast: ${type} - ${message}`);
      
      // 如果使用Vue组件，尝试使用其$toast API
      // 注意：Vue实例上可能未挂载$toast
      try {
        if (window?.$toast) {
          window.$toast[type](message);
        } else {
          // 降级处理：仅记录日志
          console.log(`[Toast] ${type}: ${message}`);
          
          // 为了确保用户体验，将消息通过事件分发给RoomView组件自行处理
          document.dispatchEvent(new CustomEvent('room-toast', { 
            detail: { type, message } 
          }));
        }
      } catch (error) {
        console.error('[RoomStore] 显示Toast失败:', error);
        console.log(`[Toast Fallback] ${type}: ${message}`);
      }
    },
    setGodPollingStatus(isPolling) {
      console.log(`[RoomStore] 设置上帝轮询状态: ${isPolling}`);
      this.isGodPolling = isPolling;
    },
    setRoleInfo(roleData) {
      console.log('[RoomStore] 设置角色信息', roleData);
      
      // 保存角色信息
      this.roles = roleData.roles || {};
      this.currentRole = roleData.role || '';
      this.spyTeammates = roleData.spy_teammates || [];
      
      // 根据角色类型处理词语
      if (this.currentRole === 'civilian') {
        // 这里平民的词语从 civilian_word 中获取
        this.civilianWord = roleData.civilian_word || '';
        console.log('[RoomStore] 设置平民词语:', this.civilianWord);
      } else if (this.currentRole === 'spy') {
        // 间谍的词语取自 spy_word
        this.spyWord = roleData.spy_word || '';
        console.log('[RoomStore] 设置卧底词语:', this.spyWord);
      } else if (this.currentRole === 'god') {
        // 上帝知道所有词语
        this.civilianWord = roleData.civilian_word || '';
        this.spyWord = roleData.spy_word || '';
        console.log('[RoomStore] 设置上帝词语组合:', {
          civilian: this.civilianWord,
          spy: this.spyWord
        });
      }
      
      // 设置游戏状态相关信息
      if (roleData.current_phase) {
        this.gamePhase = roleData.current_phase;
      }
      
      if (roleData.current_round) {
        this.currentRound = parseInt(roleData.current_round);
      }
      
      // 如果有玩家列表，更新AI玩家和用户列表
      if (roleData.player_ids && Array.isArray(roleData.player_ids)) {
        this.updatePlayerListWithAI(roleData.player_ids);
      }
      
      // 如果有AI头像信息，更新AI玩家头像
      if (roleData.ai_avatars && typeof roleData.ai_avatars === 'object') {
        this.updateAiAvatars(roleData.ai_avatars);
      }
      
      // 标记游戏已开始
      this.gameStarted = true;
      
      console.log('[RoomStore] 角色分配完成，当前roles对象:', this.roles);
    },
    
    // 更新游戏阶段
    updateGamePhase(phase) {
      console.log(`[RoomStore] 更新游戏阶段: ${this.gamePhase} -> ${phase}`);
      
      if (!phase) {
        console.error('[RoomStore] 尝试更新为空的游戏阶段');
        return;
      }
      
      // 保存上一个阶段
      this.previousGamePhase = this.gamePhase;
      
      // 更新当前阶段
      this.gamePhase = phase;
      
      // 投票阶段特殊处理
      if (phase === 'voting') {
        console.log('[RoomStore] 进入投票阶段，清除之前的投票记录');
        this.clearVotes();
      }
      
      // 输出更新后的状态
      console.log('[RoomStore] 游戏阶段已更新, 当前状态:', { 
        phase: this.gamePhase,
        previousPhase: this.previousGamePhase,
        gameStarted: this.gameStarted 
      });
    },
    
    // 添加更新游戏回合的方法
    updateGameRound(round) {
      if (round) {
        this.currentRound = parseInt(round, 10) || 1;
        console.log(`[RoomStore] 当前回合更新为: ${this.currentRound}`);
      }
    },
    updatePlayerListWithAI(playerIds) {
      console.log('[RoomStore] 更新玩家列表，确保AI玩家包含在内');
      
      // 获取当前用户列表中所有ID
      const existingUserIds = new Set(this.users.map(user => user.id));
      
      // 检查是否有新玩家ID（包括AI玩家）需要添加
      for (const playerId of playerIds) {
        if (!existingUserIds.has(playerId)) {
          // 这是一个新玩家ID，很可能是AI玩家
          if (playerId.startsWith('llm_player_')) {
            // 创建一个AI玩家对象
            const aiPlayerNumber = playerId.replace('llm_player_', '');
            const aiPlayer = {
              id: playerId,
              username: `AI玩家_${aiPlayerNumber}`,
              avatar_url: '/default_room_robot_avatar.jpg',
              is_ai: true
            };
            
            // 添加到用户列表
            this.addUser(aiPlayer);
            console.log(`[RoomStore] 添加AI玩家到用户列表: ${aiPlayer.username}`);
          }
        }
      }
    },
    updateVoteCount(voteCount) {
      console.log('[RoomStore] 收到投票计数原始数据:', voteCount);
      
      if (!voteCount || typeof voteCount !== 'object') {
        console.error('[RoomStore] 无效的投票计数数据:', voteCount);
        return;
      }
      
      // 将字符串格式的数字转换为数值
      const convertedVoteCount = {};
      for (const [userId, count] of Object.entries(voteCount)) {
        // 转换为数字类型
        convertedVoteCount[userId] = parseInt(count, 10) || 0;
      }
      
      this.voteCount = convertedVoteCount;
      console.log('[RoomStore] 处理后的投票计数:', this.voteCount);
    },
    recordVote(voterId, targetId) {
      console.log(`[RoomStore] 记录投票: ${voterId} 投给 ${targetId}`);
      
      if (!voterId || !targetId) {
        console.error('[RoomStore] 投票参数无效:', { voterId, targetId });
        return;
      }
      
      this.votedPlayers = { 
        ...this.votedPlayers, 
        [voterId]: targetId 
      };
      
      console.log('[RoomStore] 更新后的投票记录:', this.votedPlayers);
    },
    clearVotes() {
      console.log('[RoomStore] 清除所有投票记录');
      this.votedPlayers = {};
      this.voteCount = {};
    },
    // 添加处理玩家淘汰的方法
    handlePlayerEliminated(playerId, playerRole) {
      console.log(`[RoomStore] 处理玩家淘汰: ${playerId}, 角色: ${playerRole}`);
      
      // 确保roles对象存在
      if (!this.roles) {
        this.roles = {};
      }
      
      // 记录被淘汰玩家的角色，确保所有人都能看到
      this.roles[playerId] = playerRole;
      
      // 在用户列表中标记该玩家为已淘汰
      const playerIndex = this.users.findIndex(user => user.id === playerId);
      if (playerIndex !== -1) {
        // 使用新对象更新用户，保持响应性
        const updatedUsers = [...this.users];
        updatedUsers[playerIndex] = {
          ...updatedUsers[playerIndex],
          eliminated: true,
          role_revealed: true, // 标记角色已公开
          role: playerRole     // 直接设置角色，便于UI显示
        };
        this.users = updatedUsers;
        console.log(`[RoomStore] 已将玩家 ${playerId} 标记为淘汰，角色已揭示: ${playerRole}`);
      }
    },
    // 添加设置遗言玩家ID的方法
    setLastWordsPlayerId(playerId) {
      console.log(`[RoomStore] 设置遗言玩家ID: ${playerId}`);
      this.lastWordsPlayerId = playerId;
    },
    
    // 设置玩家在遗言阶段是否可以发言
    setCanSpeakInLastWords(canSpeak) {
      console.log(`[RoomStore] 设置玩家在遗言阶段是否可以发言: ${canSpeak}`);
      this.canSpeakInLastWords = canSpeak;
    },
    
    // 清除遗言相关状态
    clearLastWordsState() {
      console.log('[RoomStore] 清除遗言相关状态');
      this.lastWordsPlayerId = null;
      this.canSpeakInLastWords = false;
    },
    
    // 添加更新AI玩家头像的方法
    updateAiAvatars(aiAvatars) {
      console.log('[RoomStore] 更新AI玩家头像:', aiAvatars);
      
      if (!aiAvatars || typeof aiAvatars !== 'object') {
        console.warn('[RoomStore] 收到的AI头像数据无效');
        return;
      }
      
      // 缓存AI玩家ID与头像URL的映射
      this.aiAvatarMapping = this.aiAvatarMapping || {};
      
      // 遍历所有AI玩家，更新头像
      for (const [aiPlayerId, avatarUrl] of Object.entries(aiAvatars)) {
        // 更新映射
        this.aiAvatarMapping[aiPlayerId] = avatarUrl;
        
        const index = this.users.findIndex(user => user.id === aiPlayerId);
        if (index !== -1) {
          console.log(`[RoomStore] 更新AI玩家 ${aiPlayerId} 的头像为 ${avatarUrl}`);
          // 创建新对象更新头像，保持响应性
          this.users = [
            ...this.users.slice(0, index),
            { ...this.users[index], avatar_url: avatarUrl },
            ...this.users.slice(index + 1)
          ];
        } else {
          console.warn(`[RoomStore] 无法找到AI玩家 ${aiPlayerId} 来更新头像`);
        }
      }
      
      // 获取ChatStore实例，更新已有的AI消息头像
      try {
        const chatStore = useChatStore();
        if (chatStore && chatStore.messages) {
          console.log('[RoomStore] 尝试更新现有AI消息的头像');
          const aiStreamMessages = chatStore.messages.filter(
            msg => msg.type === 'ai_stream' && msg.user_id && msg.user_id.startsWith('llm_player_')
          );
          
          if (aiStreamMessages.length > 0) {
            console.log(`[RoomStore] 找到 ${aiStreamMessages.length} 条AI流式消息需要更新头像`);
            
            // 遍历所有AI流式消息，使用新头像更新
            for (const msg of aiStreamMessages) {
              const aiId = msg.user_id;
              const newAvatar = this.aiAvatarMapping[aiId];
              
              if (newAvatar && msg.avatarUrl !== newAvatar) {
                console.log(`[RoomStore] 更新消息 ${msg.id} 的AI头像，AI ID: ${aiId}`);
                chatStore.updateAiStreamMessage(msg.id, { avatarUrl: newAvatar });
              }
            }
          }
        }
      } catch (error) {
        console.error('[RoomStore] 更新AI消息头像时出错:', error);
      }
    },
    // 从房间的存储中获取AI玩家的头像
    getAiAvatarById(aiPlayerId) {
      console.log('[RoomStore] 尝试获取AI玩家头像:', aiPlayerId);
      
      if (!aiPlayerId || !aiPlayerId.startsWith('llm_player_')) {
        console.warn(`[RoomStore] 参数不是有效的AI玩家ID: ${aiPlayerId}`);
        return null;
      }
      
      // 先从用户列表中找
      const userFromList = this.users.find(user => user.id === aiPlayerId);
      if (userFromList && userFromList.avatar_url && userFromList.avatar_url !== '/default_room_robot_avatar.jpg') {
        console.log(`[RoomStore] 从用户列表找到AI玩家 ${aiPlayerId} 头像: ${userFromList.avatar_url}`);
        return userFromList.avatar_url;
      }
      
      return null;
    },
    // 添加重置游戏状态的方法
    resetGameState() {
      console.log('[RoomStore] 重置游戏状态为初始状态');
      
      // 重置游戏相关状态
      this.gameStarted = false;
      this.roles = null;
      this.currentRole = '';
      this.spyTeammates = [];
      this.gamePhase = '';
      this.currentRound = 0;
      this.civilianWord = '';
      this.spyWord = '';
      this.voteCount = {};
      this.votedPlayers = {};
      this.lastWordsPlayerId = null;
      this.canSpeakInLastWords = false;
      this.previousGamePhase = null;
      
      // 清除所有玩家的淘汰状态和角色信息
      if (this.users && this.users.length > 0) {
        // 过滤掉AI玩家，只保留真实玩家
        this.users = this.users
          .filter(user => !user.id.startsWith('llm_player_'))
          .map(user => ({
            ...user,
            eliminated: false,
            role_revealed: false,
            role: undefined
          }));
      }
      
      // 如果房间信息存在，更新状态
      if (this.roomInfo) {
        this.roomInfo.status = 'waiting';
      }
      
      console.log('[RoomStore] 游戏状态已重置为初始状态');
    },
  },
  getters: {
    gameNotStarted(state) {
        return state.roomInfo?.status !== 'playing';
    },
    secretChatTargets(state) {
        const userStore = useUserStore();
        return state.users.filter(user => user.id !== userStore.currentUser?.id);
    }
  },
}) 