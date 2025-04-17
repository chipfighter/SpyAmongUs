<template>
  <div class="room-container">
    <!-- 加载状态 -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">{{ loadingText }}</div>
    </div>
    
    <!-- 顶部标题栏 (现在使用组件) -->
    <RoomHeader v-if="roomInfo"
      :room-info="roomInfo" 
      :connection-status="connectionStatus" 
      :is-host="isHost"
      @copy-invite-code="copyInviteCode"
      @back-to-lobby="backToLobby"
      @leave-room="handleLeaveRoom"
      @disband-room="handleDisbandRoom"
    />

    <!-- 悬浮球 (现在使用组件) -->
    <FloatingBall v-if="roomInfo"
      :show="showFloatingBall" 
      :room-name="roomInfo.name" 
      :position="floatingBallPosition"
      @start-drag="handleStartDragBall"
      @clicked="handleFloatingBallClick"
    />

    <!-- 简易聊天框 (现在使用组件) -->
    <MiniChat v-if="roomInfo"
      :show="showMiniChat"
      :room-name="roomInfo.name"
      :messages="chatStore.miniChatMessages" 
      v-model:newMessage="miniChatMessage"
      :is-connected="wsConnected"
      @close="handleCloseMiniChat"
      @send-message="handleSendMiniChatMessage"
    />

    <div class="room-content" v-if="roomInfo">
      <!-- 聊天区域 -->
      <div class="chat-container">
        <!-- 消息列表 (现在使用组件) -->
        <ChatMessageList v-if="currentUser"
          :messages="chatMessages"
          :current-user-id="currentUser.id"
          :users="roomUsers" 
          :current-user-avatar="currentUser.avatar_url"
        />

        <!-- 输入框 (现在使用组件) -->
        <ChatInput v-if="currentUser"
          ref="chatInputRef"
              v-model="newMessage" 
          :is-connected="wsConnected"
          :users="roomUsers"
          :current-user-id="currentUser.id"
          @send-message="handleSendMessage"
        />
              </div>
              
              <!-- 用户列表 -->
      <UserList v-if="currentUser"
        :users="roomUsers"
        :host-id="roomInfo.host_id"
        :total-players="roomInfo.total_players"
        :current-user-id="currentUser.id"
        :ready-users="readyUsers"
        :game-started="gameStarted"
        :is-ready="isReady"
        :is-collapsed="isUserListCollapsed"
        @toggle-collapse="handleToggleUserListCollapse" 
        @toggle-ready="toggleReady" 
        @toggle-secret-chat="toggleSecretChat"
        @start-resize="handleStartResize"
      />
      </div>
      <!-- 如果 roomInfo 不存在时显示的消息 -->
      <div v-else class="room-content-loading">
          正在加载房间数据...
      </div>

    <!-- 秘密聊天模态框 (现在使用组件) -->
    <SecretChatModal 
      :show="showSecretChat" 
      :messages="secretChatMessages"
      :current-user="currentUser"
      :targets="secretChatTargets"
      v-model:selectedTargets="selectedTargets"
      v-model:newMessage="newSecretMessage"
      :is-connected="wsConnected"
      :room-users="roomUsers" 
      @close="toggleSecretChat" 
      @send-message="sendSecretMessage"
      @toggle-target="toggleTargetUser" 
    />

    <!-- 错误提示模态框 -->
    <div v-if="roomStore.error" class="error-modal-overlay">
      <div class="error-modal">
        <div class="error-modal-header">
          <h3>提示</h3>
          <button class="close-button" @click="roomStore.clearError()">×</button>
        </div>
        <div class="error-modal-content">
          <p>{{ roomStore.error }}</p>
        </div>
        <div class="error-modal-footer">
          <button @click="roomStore.clearError()">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AiStreamMessage from '@/components/Room/AiStreamMessage.vue'; // 确认路径正确
import UserList from '@/components/Room/UserList.vue';
import ChatMessageList from '@/components/Room/ChatMessageList.vue';
import ChatInput from '@/components/Room/ChatInput.vue'; // --- 导入新组件 ---
import RoomHeader from '@/components/Room/RoomHeader.vue'; // --- 导入新组件 ---
import SecretChatModal from '@/components/Room/SecretChatModal.vue'; // --- 导入新组件 ---
import FloatingBall from '@/components/Room/FloatingBall.vue'; // --- 导入新组件 ---
import MiniChat from '@/components/Room/MiniChat.vue';       // --- 导入新组件 ---
import { useUserStore } from '@/stores/userStore.js'; // --- 导入 userStore ---
import { useWebsocketStore } from '@/stores/websocket.js'; // --- 导入 websocketStore ---
import { useChatStore } from '@/stores/chat.js'; // --- 导入 chatStore ---
import { useRoomStore } from '@/stores/room.js'; // --- 导入 roomStore ---

export default {
  name: 'RoomView',
  components: {
    AiStreamMessage,
    UserList,
    ChatMessageList,
    ChatInput,
    RoomHeader,
    SecretChatModal,
    FloatingBall,   // --- 注册新组件 ---
    MiniChat        // --- 注册新组件 ---
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const userStore = useUserStore(); 
    const websocketStore = useWebsocketStore(); // --- 获取 websocketStore 实例 ---
    const chatStore = useChatStore(); // --- 获取 chatStore 实例 ---
    const roomStore = useRoomStore(); // --- 获取 roomStore 实例 ---
    
    // --- 将 roomStore 的状态和方法映射到组件中 ---
    // (注意：这里我们还是返回整个 store 实例，在 Options API 中通过 this 访问)
    // 如果完全使用 Composition API，可以在这里解构或返回需要的 state/actions
    
    return { route, router, userStore, websocketStore, chatStore, roomStore }; // --- 返回 roomStore ---
  },
  data() {
    return {
      newMessage: '',
      showMentionPopup: false,
      mentionQuery: '',
      mentionStartIndex: -1,
      filteredMentionUsers: [],
      selectedMentionIndex: 0,
      showAiAssistant: true,
      showFloatingBall: false,
      showMiniChat: false,
      floatingBallPosition: {
        top: '100px',
        left: '20px'
      },
      isDragging: false,
      dragOffset: { x: 0, y: 0 },
      miniChatMessage: '',
      isUserListCollapsed: false,
      currentAiMessage: {
        content: '',
        isStreaming: false,
        timestamp: 0
      },
      currentAiStreamSession: null,
      secretChatTargets: [],
      selectedTargets: [],
      newSecretMessage: ''
    }
  },
  computed: {
    // Map user store state
    currentUser() {
      return this.userStore.user;
    },
    // Map websocket store state
    connectionStatus() {
      return this.websocketStore.connectionStatus;
    },
    wsConnected() {
      return this.websocketStore.isConnected;
    },
    // Map chat store state
    chatMessages() {
      return this.chatStore.messages;
    },
    secretChatMessages() {
      return this.chatStore.secretMessages;
    },
    // Map room store state and getters needed by the template
    isLoading() {
      return this.roomStore.isLoading; // Map isLoading
    },
    loadingText() {
      return this.roomStore.loadingText; // Map loadingText
    },
    roomInfo() {
      return this.roomStore.roomInfo; // Map roomInfo
    },
    roomUsers() {
      return this.roomStore.users; // Map room users
    },
    readyUsers() {
      return this.roomStore.readyUsers; // Map ready users
    },
    gameStarted() {
      return this.roomStore.gameStarted; // Map game started flag
    },
    isReady() {
      return this.roomStore.isCurrentUserReady; // Map current user ready state
    },
    showSecretChat() {
      return this.roomStore.showSecretChatModal; // Assuming you add this state to roomStore later or manage locally
    },
    // Map room store getters
    isHost() {
      // --- Direct comparison logic --- 
      const isHostResult = !!(this.userStore.user?.id && this.roomStore.roomInfo?.host_id && this.userStore.user.id === this.roomStore.roomInfo.host_id);
      console.log('[RoomView Computed isHost] Direct Check:', { 
          hostId: this.roomStore.roomInfo?.host_id, 
          currentUserId: this.userStore.user?.id, 
          isHostResult 
      });
      return isHostResult;
    },
    gameNotStarted() {
      return this.roomStore.gameNotStarted;
    },
    secretChatTargetsComputed() {
        // Keep this if secret chat targets logic remains complex in the store getter
        return this.roomStore.secretChatTargets;
        // Or simplify if local data `secretChatTargets` is sufficient
        // return this.secretChatTargets;
    }
  },
  async created() {
    const roomId = this.route.params.roomId;
    if (!roomId) {
      console.error("Room ID not found in route params.");
      this.router.push('/lobby');
      return;
    }
    
    // 只获取房间详情
    const success = await this.roomStore.fetchRoomDetails(roomId);
    
    if (!success) {
        console.error("Failed to fetch room details in created hook.");
        // 可以在这里设置一个错误状态，而不是直接跳转
        // 比如 this.error = '无法加载房间信息';
        // 或者让 roomStore 处理错误并显示
        this.router.push('/lobby'); // 暂时保留跳转逻辑
    } 
    // --- WebSocket 连接逻辑已移除 ---
  },
  mounted() {
    // Mounted hook is now empty, connection logic moved to watcher
    console.log("[RoomView Mounted] Hook executed. Waiting for roomInfo to connect WebSocket.");
  },
  watch: {
    // Watch the roomInfo computed property
    roomInfo: {
      handler(newRoomInfo, oldRoomInfo) {
        console.log("[RoomView Watcher] roomInfo changed:", newRoomInfo);
        // Check if roomInfo is now valid and wasn't before (or first load)
        if (newRoomInfo && newRoomInfo.invite_code && (!oldRoomInfo || !oldRoomInfo.invite_code)) {
          // --- Connection logic is now handled before navigation --- 
          // --- We can simply log the status here for debugging --- 
          console.log(`[RoomView Watcher] Room info loaded. Checking WS status: ${this.websocketStore.connectionStatus}`);
          if (!this.websocketStore.isConnected) {
            console.warn('[RoomView Watcher] Warning: Entered room but WebSocket is not connected. This might indicate an issue.');
            // Optionally trigger an error or attempt reconnect based on app logic
            // For now, we just warn.
          }
        } else if (!newRoomInfo && oldRoomInfo) {
             console.log("[RoomView Watcher] roomInfo became null/undefined.");
             // Optionally handle room data being cleared, e.g., disconnect WebSocket if needed
             if (this.websocketStore.isConnected) { 
                 console.log('[RoomView Watcher] Room info cleared, disconnecting WebSocket.');
                 this.websocketStore.disconnect(); 
             }
        }
      },
      immediate: true, // Keep immediate true to check status on load
      deep: false 
    }
  },
  beforeUnmount() {
    console.log('组件卸载，清理资源');
    this.websocketStore.disconnect();
    this.roomStore.clearRoomState();
  },
  methods: {
    async handleLeaveRoom() {
        const success = await this.roomStore.leaveRoom();
        if (success) {
            alert('已成功退出房间');
            this.router.push('/lobby');
        } else {
             alert(`退出房间失败: ${this.roomStore.error || '请稍后重试'}`);
        }
    },
    async handleDisbandRoom() {
        const success = await this.roomStore.disbandRoom();
        if (success) {
             alert('房间已成功解散');
             this.router.push('/lobby');
          } else {
             alert(`解散房间失败: ${this.roomStore.error || '请稍后重试'}`);
        }
    },
    copyInviteCode() {
      if (this.roomStore.roomInfo?.invite_code) {
          navigator.clipboard.writeText(this.roomStore.roomInfo.invite_code)
            .then(() => {
              alert('邀请码已复制到剪贴板！');
            })
            .catch(err => {
              console.error('复制失败:', err);
            });
          } else {
          alert('无法复制邀请码');
      }
    },
    handleSendMessage() {
      this.sendMessage();
    },
    saveActiveRoomState() {
      const roomState = {
        invite_code: this.roomStore.roomInfo?.invite_code,
        name: this.roomStore.roomInfo?.name,
        position: this.floatingBallPosition,
        connection_status: this.websocketStore.connectionStatus,
        host_id: this.roomStore.roomInfo?.host_id,
        messages: this.chatStore.messages.slice(-50),
        secretMessages: this.chatStore.secretMessages.slice(-50)
      };
      localStorage.setItem('active_room', JSON.stringify(roomState));
      console.log('房间状态已保存到 localStorage', roomState);
    },
    handleStartDragBall(event) {
        if (!this.showFloatingBall) return;

        this.isDragging = true;
        const startX = event.clientX;
        const startY = event.clientY;
        const initialTop = parseFloat(this.floatingBallPosition.top) || 0;
        const initialLeft = parseFloat(this.floatingBallPosition.left) || 0;

        const handleMouseMove = (moveEvent) => {
            if (!this.isDragging) return;
            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;
            
            let newTop = initialTop + deltaY;
            let newLeft = initialLeft + deltaX;
            
            const ballSize = 60;
            newTop = Math.max(0, Math.min(newTop, window.innerHeight - ballSize));
            newLeft = Math.max(0, Math.min(newLeft, window.innerWidth - ballSize));
            
            this.floatingBallPosition = {
                top: `${newTop}px`,
                left: `${newLeft}px`
            };
        };

        const handleMouseUp = () => {
            this.isDragging = false;
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            this.saveActiveRoomState(); 
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    },
    handleFloatingBallClick() {
      if (!this.isDragging) {
          this.showFloatingBall = false;
          this.showMiniChat = true;
          this.saveActiveRoomState();
      }
    },
    handleCloseMiniChat() {
        this.showMiniChat = false;
        this.showFloatingBall = true;
        this.saveActiveRoomState();
    },
    handleSendMiniChatMessage() {
      if (!this.miniChatMessage.trim()) return;
      
      const originalMessage = this.newMessage;
      this.newMessage = this.miniChatMessage;
      this.sendMessage();
      this.miniChatMessage = '';
      this.newMessage = originalMessage;
    },
    handleToggleUserListCollapse() {
      this.isUserListCollapsed = !this.isUserListCollapsed;
      if (this.isUserListCollapsed) {
        const usersContainer = this.$el.querySelector('.users-container');
        if (usersContainer) {
          
        }
      }
    },
    handleStartResize(event) {
      if (this.isUserListCollapsed) return;
      
      event.stopPropagation();
      event.preventDefault();
      
      const usersContainer = this.$el?.querySelector('.users-container'); 
      if (!usersContainer) {
          console.warn("Cannot find .users-container element for resizing");
            return;
          }
          
      const initialX = event.clientX;
      const initialWidth = usersContainer.offsetWidth;
      
      const minWidth = 200;
      const maxWidth = 500;
      
      usersContainer.classList.add('resizing');
      
      const handleMouseMove = (moveEvent) => {
        const deltaX = initialX - moveEvent.clientX;
        let newWidth = initialWidth + deltaX;
        if (newWidth < minWidth) newWidth = minWidth;
        if (newWidth > maxWidth) newWidth = maxWidth;
        usersContainer.style.width = `${newWidth}px`;
      };
      
      const handleMouseUp = () => {
        usersContainer.classList.remove('resizing');
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
      
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    toggleReady() {
        this.roomStore.toggleReady(); 
    },
    sendMessage() {
      if (!this.newMessage.trim()) return;
      
      if (this.connectionStatus !== 'connected' || !this.wsConnected) {
        this.roomStore.setError('网络连接已断开，请刷新页面重试');
        return;
      }
      
      const mentions = [];
      const mentionRegex = /@\[([^:]+):([^\]]+)\]/g;
      let match;
      let aiType = null;
      
      while ((match = mentionRegex.exec(this.newMessage)) !== null) {
        const userId = match[1];
        const username = match[2];
        
        if (userId === 'ai_assistant') {
          aiType = 'deepseekv3';
          mentions.push({
            id: userId,
            name: username
          });
        } else {
          mentions.push({
            id: userId,
            name: username
          });
        }
      }
      
      const message = {
        type: 'chat',
        content: this.newMessage.trim(),
        user_id: this.currentUser?.id,
        username: this.currentUser?.username,
        timestamp: Date.now(),
        is_system: false,
        round: "0",
        mentions: mentions,
        ai_type: aiType,
        room_id: this.roomStore.roomInfo.invite_code
      };
      
      console.log("发送消息:", JSON.stringify(message));
      
      if (!this.websocketStore.sendMessage(message)) {
        this.roomStore.setError('发送消息失败，请检查网络连接');
      } else {
        this.newMessage = '';
      }
      
      this.$nextTick(() => {
        const chatInputComponent = this.$refs.chatInputRef;
        if (chatInputComponent && chatInputComponent.adjustTextareaHeight) {
          chatInputComponent.adjustTextareaHeight();
        }
      });
    },
    toggleSecretChat() {
      this.showSecretChat = !this.showSecretChat;
      if (!this.showSecretChat) {
        this.selectedTargets = [];
        this.newSecretMessage = '';
      }
    },
    toggleTargetUser(userId) {
      const index = this.selectedTargets.indexOf(userId);
      if (index === -1) {
        this.selectedTargets.push(userId);
      } else {
        this.selectedTargets.splice(index, 1);
      }
    },
    sendSecretMessage() {
      if (!this.newSecretMessage.trim() || this.selectedTargets.length === 0) return;
      
      if (this.connectionStatus !== 'connected' || !this.wsConnected) {
        this.roomStore.setError('网络连接已断开，请刷新页面重试');
        return;
      }
      
      const message = {
        type: 'secret',
        content: this.newSecretMessage.trim(),
        user_id: this.currentUser?.id,
        username: this.currentUser?.username,
        timestamp: Date.now(),
        is_system: false,
        round: "0",
        target_users: this.selectedTargets,
        room_id: this.roomStore.roomInfo.invite_code
      };
      
      console.log("发送秘密消息:", JSON.stringify(message));
      
      if (!this.websocketStore.sendMessage(message)) {
        this.roomStore.setError('发送秘密消息失败，请检查网络连接');
      }
    },
    backToLobby() {
      this.saveActiveRoomState(); 
      
      this.showFloatingBall = true; 
      this.showMiniChat = false;
      
      this.router.push('/lobby?in_room=true');
    },
  }
}
</script>

<style scoped>
.room-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f0f2f5;
}

.room-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(255, 255, 255, 0.8);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: 5px solid #f3f3f3;
  border-top: 5px solid #1890ff;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

.loading-text {
  font-size: 18px;
  color: #333;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.error-modal {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  max-width: 400px;
  width: 100%;
}

.error-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.error-modal-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-button {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
}

.error-modal-content {
  margin-bottom: 10px;
}

.error-modal-footer {
  display: flex;
  justify-content: flex-end;
}

.error-modal-footer button {
  padding: 8px 16px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
</style> 