import { defineStore } from 'pinia'
import { useUserStore } from './userStore'
import { useWebsocketStore } from './websocket'
import { useChatStore } from './chat'

// 初始状态工厂函数，方便重置
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
        // --- 添加日志：检查 token --- 
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
          // --- Add logs to verify state update ---
          console.log('[RoomStore] State updated after fetch:');
          console.log('[RoomStore] this.roomInfo:', JSON.stringify(this.roomInfo));
          console.log('[RoomStore] this.users:', JSON.stringify(this.users));
          // ---------------------------------------
          this.isLoading = false;
          return true; // Indicate success
        } else {
          throw new Error(result.message || '获取房间信息失败');
        }
      } catch (error) {
        console.error('[RoomStore] Fetch room details failed:', error);
        this.error = error.message;
        this.isLoading = false;
        return false; // Indicate failure
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
                websocketStore.disconnect(); // Disconnect WebSocket
                this.clearRoomState(); // Clear local state
                this.isLoading = false;
                return true; // Indicate success for routing
            } else {
                throw new Error(result.message || '退出房间失败');
            }
        } catch (error) {
            console.error('[RoomStore] Leave room failed:', error);
            this.error = error.message;
            this.isLoading = false;
            return false; // Indicate failure
        }
    },
    async disbandRoom() {
        // --- Add Pre-Check Logging ---
        const userStoreForCheck = useUserStore();
        const hostId = this.roomInfo?.host_id;
        const currentUserId = userStoreForCheck.user?.id;
        const isHostCheck = hostId === currentUserId;
        console.log(`[RoomStore Pre-Disband Check] Invite Code: ${this.roomInfo?.invite_code}, Host ID: ${hostId}, Current User ID: ${currentUserId}, Is Host: ${isHostCheck}`);
        // -----------------------------

        // --- Original Guard Condition --- 
        if (!this.roomInfo?.invite_code || !isHostCheck) { 
            console.warn('[RoomStore Disband] Guard condition failed or user is not host.');
            // Optionally set error message here if needed
            // this.setError('无法解散房间：不是房主或房间信息错误');
            return false; 
        }
        // -----------------------------

        console.log(`[RoomStore] Disbanding room ${this.roomInfo.invite_code}`);
        this.isLoading = true;
        this.loadingText = '正在解散房间...';
        this.error = null;
        const userStore = useUserStore();
        const websocketStore = useWebsocketStore();

        try {
            // --- Add Pre-Fetch Logging ---
            const apiUrl = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${this.roomInfo.invite_code}/delete_room`;
            const accessToken = userStore.accessToken;
            console.log(`[RoomStore Pre-Fetch] URL: ${apiUrl}, Token Exists: ${!!accessToken}`);
            // -----------------------------

            const response = await fetch(apiUrl, {
                method: 'POST', 
                headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
                }
            });
            
            // --- Add Post-Fetch Logging ---
            console.log(`[RoomStore Post-Fetch] Response status: ${response.status}`);
            // -----------------------------

            const result = await response.json();
             if (result.success) {
                console.log('[RoomStore] Disbanded room successfully');
                websocketStore.disconnect(); // Disconnect WebSocket
                this.clearRoomState(); // Clear local state
                this.isLoading = false;
                return true; // Indicate success for routing
            } else {
                throw new Error(result.message || '解散房间失败');
            }
        } catch (error) {
            console.error('[RoomStore] Disband room failed:', error);
            // --- Log the full error object --- 
            console.error('[RoomStore] Full error object:', error); 
            // ------------------------------------
            this.error = error.message;
            this.isLoading = false;
            return false; // Indicate failure
        }
    },

    // --- WebSocket Event Handlers (called by websocketStore) ---
    setRoomInfo(data) {
      console.log('[RoomStore] Setting room info:', data);
      this.roomInfo = { ...this.roomInfo, ...data };
    },
    updateUserList(users) {
      console.log('[RoomStore] Updating user list:', users);
      // --- Add detailed logging ---
      if (Array.isArray(users)) {
        console.log(`[RoomStore] Received ${users.length} users. Details:`);
        users.forEach((user, index) => {
          console.log(`  User ${index}: id=${user?.id}, username=${user?.username}, avatar_url=${user?.avatar_url}`);
        });
      } else {
        console.warn('[RoomStore] Received non-array data for user list:', users);
      }
      // --- End detailed logging ---
      this.users = users || [];
    },
    setHost(newHostId) {
      console.log(`[RoomStore] Setting new host: ${newHostId}`);
       if (this.roomInfo) {
           this.roomInfo.host_id = newHostId;
       }
    },
    updateReadyStatus(payload) {
        console.log('[RoomStore] Updating ready status:', payload);
        const { user_id, is_ready } = payload;
        const userStore = useUserStore();
        
        if (user_id === userStore.currentUser?.id) {
            this.isCurrentUserReady = is_ready;
        }
        
        const index = this.readyUsers.indexOf(user_id);
        if (is_ready && index === -1) {
            this.readyUsers.push(user_id);
        } else if (!is_ready && index !== -1) {
            this.readyUsers.splice(index, 1);
        }
    },
    setGameStatus(started) {
        console.log(`[RoomStore] Setting game status to: ${started}`);
      this.gameStarted = started;
      if (!started) {
        // Reset ready status on game end
        this.readyUsers = [];
        this.isCurrentUserReady = false;
      }
    },

    // --- Component Actions ---
    async toggleReady() {
        const userStore = useUserStore();
        const websocketStore = useWebsocketStore();
        if (!websocketStore.isConnected || !userStore.currentUser?.id || !this.roomInfo.invite_code) {
            console.warn('[RoomStore] Cannot toggle ready: Not connected or user/room info missing');
            return;
        }
        
        const newReadyState = !this.isCurrentUserReady;
        console.log(`[RoomStore] Toggling ready state for user ${userStore.currentUser.id} to ${newReadyState}`);
        
        // Optimistically update UI
        this.isCurrentUserReady = newReadyState;
        const userId = userStore.currentUser.id;
        const index = this.readyUsers.indexOf(userId);
        if (newReadyState && index === -1) {
            this.readyUsers.push(userId);
        } else if (!newReadyState && index !== -1) {
            this.readyUsers.splice(index, 1);
        }
        
        // Send update to backend
        const readyMessage = {
           type: 'ready_status',
           user_id: userId,
           is_ready: newReadyState,
           room_id: this.roomInfo.invite_code
         };
        if (!websocketStore.sendMessage(readyMessage)) {
             console.error('[RoomStore] Failed to send ready status update');
             // Revert optimistic update on failure?
             this.isCurrentUserReady = !newReadyState;
             const revertIndex = this.readyUsers.indexOf(userId);
             if (newReadyState && revertIndex !== -1) this.readyUsers.splice(revertIndex, 1);
             if (!newReadyState && revertIndex === -1) this.readyUsers.push(userId);
             this.setError('发送准备状态失败');
        }
    },
    setError(message) {
      console.error('[RoomStore] Error set:', message);
      this.error = message;
      // Optionally clear error after some time
      // setTimeout(() => { this.error = null; }, 5000);
    },
    clearError() {
        console.log('[RoomStore] Clearing error');
        this.error = null;
    },
    // --- State Management ---
    clearRoomState() {
      console.log('[RoomStore] Clearing room state');
      Object.assign(this, getDefaultState());
      // Also clear related stores?
      // useChatStore().clearMessages(); 
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