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
  loadingText: '',
  error: null,
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
      console.log('[RoomStore] Clearing room state');
      Object.assign(this, getDefaultState());
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