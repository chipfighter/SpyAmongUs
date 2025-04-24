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
      <!-- 侧栏组件 -->
      <RoomSidebar 
        :room-info="roomInfo"
        :users="roomUsers"
        @copy-invite-code="copyInviteCode"
        :is-collapsed="isSidebarCollapsed"
        @toggle-collapse="handleToggleSidebar"
      />
      
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
        @add-friend="handleAddFriend"
        @view-user-details="handleViewUserDetails"
        @private-message="handlePrivateMessage" 
        @kick-user="handleKickUser"
        :is-host="isHost"
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

    <!-- 倒计时动画组件 -->
    <CountdownOverlay ref="countdownOverlay" @cancel-ready="handleCancelReady" />

    <!-- 上帝角色询问弹窗 -->
    <GodRoleInquiryModal
      :visible="showGodRoleInquiry"
      :message="godRoleInquiryMessage"
      :timeout="godRoleInquiryTimeout"
      @accept="handleAcceptGodRole"
      @decline="handleDeclineGodRole"
      @timeout="handleGodRoleTimeout"
    />

    <!-- 上帝角色询问状态弹窗（给普通用户显示） -->
    <GodRoleInquiryStatusModal
      :visible="showGodRoleInquiryStatus"
      :message="godRoleInquiryStatusMessage"
      :timeout="godRoleInquiryStatusTimeout"
      :username="godRoleInquiryStatusUsername"
    />

    <!-- 上帝选词弹窗 -->
    <GodWordSelectionModal
      :visible="showGodWordSelection"
      :message="godWordSelectionMessage"
      :timeout="godWordSelectionTimeout"
      @confirm="handleGodWordSelectionConfirm"
      @timeout="handleGodWordSelectionTimeout"
    />

    <!-- 上帝选词状态弹窗（给普通用户显示） -->
    <GodWordSelectionStatusModal
      :visible="showGodWordSelectionStatus"
      :message="godWordSelectionStatusMessage"
      :timeout="godWordSelectionStatusTimeout"
      :godUsername="godWordSelectionStatusUsername"
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

    <!-- 游戏加载动画 -->
    <GameLoadingOverlay 
      :visible="showGameLoading" 
      :title="gameLoadingTitle"
      :message="gameLoadingMessage"
    />
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
import RoomSidebar from '@/components/Room/RoomSidebar.vue'; // --- 导入侧栏组件 ---
import { useUserStore } from '@/stores/userStore.js'; // --- 导入 userStore ---
import { useWebsocketStore } from '@/stores/websocket.js'; // --- 导入 websocketStore ---
import { useChatStore } from '@/stores/chat.js'; // --- 导入 chatStore ---
import { useRoomStore } from '@/stores/room.js'; // --- 导入 roomStore ---
import CountdownOverlay from '@/components/Room/CountdownOverlay.vue'; // --- 导入 CountdownOverlay 组件 ---
import GodRoleInquiryModal from '@/components/Room/GodRoleInquiryModal.vue'; // --- 导入 GodRoleInquiryModal 组件 ---
import GodWordSelectionModal from '@/components/Room/GodWordSelectionModal.vue'; // --- 导入 GodWordSelectionModal 组件 ---
import GodWordSelectionStatusModal from '@/components/Room/GodWordSelectionStatusModal.vue'; // --- 导入 GodWordSelectionStatusModal 组件 ---
import GodRoleInquiryStatusModal from '@/components/Room/GodRoleInquiryStatusModal.vue'; // --- 导入 GodRoleInquiryStatusModal 组件 ---
import GameLoadingOverlay from '@/components/Room/GameLoadingOverlay.vue';

export default {
  name: 'RoomView',
  components: {
    AiStreamMessage,
    UserList,
    ChatMessageList,
    ChatInput,
    RoomHeader,
    SecretChatModal,
    FloatingBall,
    MiniChat,
    RoomSidebar,
    CountdownOverlay,
    GodRoleInquiryModal,
    GodWordSelectionModal,
    GodWordSelectionStatusModal,
    GodRoleInquiryStatusModal,
    GameLoadingOverlay
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const userStore = useUserStore(); 
    const websocketStore = useWebsocketStore(); // --- 获取 websocketStore 实例 ---
    const chatStore = useChatStore(); // --- 获取 chatStore 实例 ---
    const roomStore = useRoomStore(); // --- 获取 roomStore 实例 ---
    
    // --- 将 roomStore 的状态和方法映射到组件中 ---
    // 如果完全使用 Composition API，可以在这里解构或返回需要的 state/actions
    
    // 游戏加载状态
    const showGameLoading = ref(false);
    const gameLoadingTitle = ref('游戏初始化中');
    const gameLoadingMessage = ref('正在准备游戏环境，请稍候...');
    
    return { route, router, userStore, websocketStore, chatStore, roomStore, showGameLoading, gameLoadingTitle, gameLoadingMessage }; // --- 返回 roomStore ---
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
      isSidebarCollapsed: true,
      currentAiMessage: {
        content: '',
        isStreaming: false,
        timestamp: 0
      },
      currentAiStreamSession: null,
      secretChatTargets: [],
      selectedTargets: [],
      newSecretMessage: '',
      ws: null,
      isConnected: false,
      pingTimer: null,
      showGodRoleInquiry: false,
      godRoleInquiryMessage: '',
      godRoleInquiryTimeout: 7,
      showGodRoleInquiryStatus: false,
      godRoleInquiryStatusMessage: '',
      godRoleInquiryStatusTimeout: 7,
      godRoleInquiryStatusUsername: '',
      showGodWordSelection: false,
      godWordSelectionMessage: '',
      godWordSelectionTimeout: 7,
      showGodWordSelectionStatus: false,
      godWordSelectionStatusMessage: '',
      godWordSelectionStatusTimeout: 7,
      godWordSelectionStatusUsername: ''
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
      // --- Remove Direct Check Logging --- 
      const isHostResult = !!(this.userStore.user?.id && this.roomStore.roomInfo?.host_id && this.userStore.user.id === this.roomStore.roomInfo.host_id);
      /* console.log('[RoomView Computed isHost] Direct Check:', { 
          hostId: this.roomStore.roomInfo?.host_id, 
          currentUserId: this.userStore.user?.id, 
          isHostResult 
      }); */
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
    
    // 添加自定义事件监听器来处理上帝角色询问
    document.addEventListener('god-role-inquiry', this.handleGodRoleInquiryEvent);
    
    // 添加上帝角色询问状态事件监听器
    document.addEventListener('god-role-inquiry-status', this.handleGodRoleInquiryStatusEvent);
    
    // 添加Toast消息事件监听
    document.addEventListener('room-toast', this.handleRoomToastEvent);
  },
  mounted() {
    // Mounted hook is now empty, connection logic moved to watcher
    console.log("[RoomView Mounted] Hook executed. Waiting for roomInfo to connect WebSocket.");
    
    // 添加事件监听
    document.addEventListener('god-words-selection', this.handleGodWordSelectionEvent);
    document.addEventListener('god-words-selected', this.handleGodWordsSelectedEvent);
    
    // 确保已添加上帝角色询问状态监听器（如果在created中没有注册）
    document.removeEventListener('god-role-inquiry-status', this.handleGodRoleInquiryStatusEvent); // 先移除以防重复
    document.addEventListener('god-role-inquiry-status', this.handleGodRoleInquiryStatusEvent);
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
    
    // 检查是否是临时返回大厅（从URL参数判断）
    const keepConnection = this.$route.query.keep_connection === 'true';
    
    if (!keepConnection) {
      // 只有在非临时返回大厅的情况下才断开WebSocket
      console.log('[RoomView] 组件卸载，断开WebSocket连接');
      this.websocketStore.disconnect();
      this.roomStore.clearRoomState();
    } else {
      console.log('[RoomView] 临时返回大厅，保持WebSocket连接');
      // 不清除房间状态，保持连接
    }
    
    // 移除事件监听器
    document.removeEventListener('god-role-inquiry', this.handleGodRoleInquiryEvent);
    
    // 移除上帝角色询问状态事件监听器
    document.removeEventListener('god-role-inquiry-status', this.handleGodRoleInquiryStatusEvent);
    
    // 移除Toast消息事件监听
    document.removeEventListener('room-toast', this.handleRoomToastEvent);
    
    // 移除上帝选词相关事件监听
    document.removeEventListener('god-words-selection', this.handleGodWordSelectionEvent);
    document.removeEventListener('god-words-selected', this.handleGodWordsSelectedEvent);
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
            
            // 直接跳转到大厅，不需要延迟
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
      console.log('[RoomView] toggleReady method called, dispatching to store...');
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
      
      // 不要断开WebSocket连接
      console.log('[RoomView] 返回大厅，保持WebSocket连接');
      
      // 在URL中添加参数，表示只是临时返回大厅
      this.router.push('/lobby?in_room=true&keep_connection=true');
    },
    handleAddFriend(userId) {
      console.log('[RoomView] 添加好友请求:', userId);
      // 暂未实现 - 将来添加好友功能
    },
    
    handleViewUserDetails(userId) {
      console.log('[RoomView] 查看用户详情:', userId);
      // 暂未实现 - 将来查看用户详情功能
    },
    
    handlePrivateMessage(userId) {
      console.log('[RoomView] 发送私信:', userId);
      // 暂未实现 - 将来可以整合当前秘密聊天功能
    },
    
    handleKickUser(userId) {
      console.log('[RoomView] 踢出用户:', userId);
      // 暂未实现 - 将来踢出用户功能
    },
    handleToggleSidebar() {
      this.isSidebarCollapsed = !this.isSidebarCollapsed;
    },
    handleWebSocketClose(event) {
      // 检查关闭代码或原因是否表明房间已被解散
      if (event.reason === 'room_closed' || event.code === 4000) {
        // 向用户显示通知，告知房间已被解散
        this.$notify({
          title: '房间已解散',
          message: '房主已解散房间，您将返回大厅',
          type: 'warning',
          duration: 3000
        });
        
        // 延迟后清理房间数据并跳转到大厅
        setTimeout(() => {
          // 清理房间数据
          localStorage.removeItem('activeRoomId');
          // 重定向到大厅页面
          this.$router.push('/lobby?refresh=true');
        }, 1000);
      }
    },
    connectWebSocket() {
      const token = localStorage.getItem('token');
      const wsUrl = `${import.meta.env.VITE_WS_URL}/ws/room/${this.roomId}?token=${token}`;
      
      console.log('[RoomView] 正在连接WebSocket...', wsUrl);
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        console.log('[RoomView] WebSocket连接已建立');
        this.isConnected = true;
        this.sendPing();
      };
      
      this.ws.onclose = (event) => {
        console.log('[RoomView] WebSocket连接已关闭', event);
        this.isConnected = false;
        clearTimeout(this.pingTimer);
        
        // 处理WebSocket连接关闭事件
        this.handleWebSocketClose(event);
      };
      
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // 确保WebSocket消息直接调用handleReceivedMessage方法处理
          this.handleReceivedMessage(data);
        } catch (error) {
          console.error('[RoomView] 处理WebSocket消息出错:', error);
        }
      }
    },
    handleCancelReady() {
      console.log('[RoomView] 用户取消准备');
      // 发送取消准备消息到后端
      if (this.isReady) {
        this.toggleReady();
      }
      
      // 通知其他用户
      const message = {
        type: 'chat',
        content: '取消了倒计时',
        user_id: this.currentUser?.id,
        username: this.currentUser?.username,
        timestamp: Date.now(),
        is_system: true,
        room_id: this.roomStore.roomInfo.invite_code
      };
      
      this.websocketStore.sendMessage(message);
    },
    handleAcceptGodRole() {
      console.log('[RoomView] 用户接受上帝角色');
      // 处理用户接受上帝角色的逻辑
      this.websocketStore.sendMessage({
        type: 'god_role_response',
        accept: true
      });
      this.showGodRoleInquiry = false;
      // 关闭所有玩家的状态弹窗 - 由服务器触发 god_role_assigned 消息
    },
    handleDeclineGodRole() {
      console.log('[RoomView] 用户拒绝上帝角色');
      // 处理用户拒绝上帝角色的逻辑
      this.websocketStore.sendMessage({
        type: 'god_role_response',
        accept: false
      });
      this.showGodRoleInquiry = false;
      // 关闭所有玩家的状态弹窗 - 由服务器触发 god_role_assigned 消息
    },
    handleGodRoleTimeout() {
      console.log('[RoomView] 上帝角色询问超时');
      // 处理上帝角色询问超时的逻辑
      // 超时视为拒绝
      this.websocketStore.sendMessage({
        type: 'god_role_response',
        accept: false,
        is_timeout: true
      });
      this.showGodRoleInquiry = false;
      // 关闭所有玩家的状态弹窗 - 由服务器触发 god_role_assigned 消息
    },
    // 处理收到的WebSocket消息
    handleReceivedMessage(message) {
      try {
        console.log('[RoomView] 接收到WS消息:', message);
        const data = typeof message === 'string' ? JSON.parse(message) : message;

        // 处理不同类型的消息
        switch(data.type) {
          // 其他case...
          
          // 处理上帝角色询问
          case 'god_role_inquiry':
            this.showGodRoleInquiry = true;
            this.godRoleInquiryMessage = data.message || '您愿意担任本局游戏的上帝吗？';
            this.godRoleInquiryTimeout = data.timeout || 7;
            break;
            
          // 处理上帝角色询问状态广播
          case 'god_role_inquiry_status':
            // 判断是否是当前用户
            if (data.current_user === this.currentUser?.id) {
              // 是当前用户，弹窗已经显示
              console.log('[RoomView] 当前正在询问我是否愿意担任上帝');
            } else {
              // 为其他用户显示询问状态弹窗 - 修复其他用户弹窗不显示的问题
              this.showGodRoleInquiryStatus = true;
              this.godRoleInquiryStatusMessage = data.message || '正在询问玩家是否愿意担任上帝...';
              this.godRoleInquiryStatusTimeout = data.timeout || 7;
              this.godRoleInquiryStatusUsername = data.username || '';
            }
            break;
            
          // 处理上帝角色分配结果
          case 'god_role_assigned':
            this.showGodRoleInquiry = false; // 关闭询问弹窗
            this.showGodRoleInquiryStatus = false; // 关闭状态弹窗
            
            if (data.is_ai) {
              this.showNotification('info', '没有玩家愿意担任上帝，本局游戏将由AI担任上帝角色');
            } else {
              this.showNotification('success', '已选定上帝角色，游戏即将开始');
            }
            break;
            
          // 处理被选为上帝的通知
          case 'you_are_god':
            this.showNotification('success', '您已被选为本局游戏的上帝');
            break;
          
          // 处理上帝选词阶段（给上帝显示）
          case 'god_words_selection':
            // 先确保所有询问弹窗关闭
            this.showGodRoleInquiry = false;
            this.showGodRoleInquiryStatus = false;
            
            // 添加小延迟，确保前一个弹窗有时间关闭
            setTimeout(() => {
              // 检查是否有god_user_id字段，如果没有说明当前用户是上帝
              if (!data.god_user_id) {
                // 当前用户是上帝，显示选词弹窗
                this.showGodWordSelection = true;
                this.godWordSelectionMessage = data.message || '请选择双方词语。';
                this.godWordSelectionTimeout = data.timeout || 30;
              } else {
                // 当前用户不是上帝，显示等待状态
                this.showGodWordSelectionStatus = true;
                this.godWordSelectionStatusMessage = data.message || '正在选词。';
                this.godWordSelectionStatusTimeout = data.timeout || 30;
                this.godWordSelectionStatusUsername = data.username || '';
              }
            }, 150); // 添加150毫秒延迟
            break;
            
          // 处理选词完成
          case 'god_words_selected':
            this.showGodWordSelection = false;
            this.showGodWordSelectionStatus = false;
            
            // 显示游戏加载动画
            this.showGameLoading = true;
            this.gameLoadingTitle = '游戏初始化中';
            this.gameLoadingMessage = '正在分配角色，请稍候...';
            break;
          
          // 处理游戏初始化完成
          case 'game_initialized':
            // 关闭游戏加载动画
            this.showGameLoading = false;
            this.showNotification('success', '游戏初始化完成，游戏开始！');
            break;
          
          // 处理更多消息类型...
          
          default:
            // 处理其他类型的消息
            console.log('[RoomView] 未处理的消息类型:', data.type);
        }
      } catch (error) {
        console.error('[RoomView] 处理WS消息时出错:', error);
      }
    },
    // 处理来自RoomStore的上帝角色询问事件
    handleGodRoleInquiryEvent(event) {
      console.log('[RoomView] 收到上帝角色询问事件:', event.detail);
      
      // 获取事件详情
      const { visible, message, timeout } = event.detail;
      
      // 更新组件状态
      this.showGodRoleInquiry = visible;
      if (visible) {
        this.godRoleInquiryMessage = message || '您愿意担任本局游戏的上帝吗？';
        this.godRoleInquiryTimeout = timeout || 7;
      }
    },
    // 处理来自RoomStore的上帝角色询问状态事件
    handleGodRoleInquiryStatusEvent(event) {
      console.log('[RoomView] 收到上帝角色询问状态事件:', event.detail);
      
      // 获取事件详情
      const { visible, message, timeout, username } = event.detail;
      
      // 更新组件状态
      this.showGodRoleInquiryStatus = visible;
      if (visible) {
        this.godRoleInquiryStatusMessage = message || '正在询问玩家是否愿意担任上帝...';
        this.godRoleInquiryStatusTimeout = timeout || 7;
        this.godRoleInquiryStatusUsername = username || '';
      }
    },
    // 处理来自RoomStore的Toast消息事件
    handleRoomToastEvent(event) {
      console.log('[RoomView] 收到房间Toast事件:', event.detail);
      
      // 获取事件详情
      const { type, message } = event.detail;
      
      // 使用自己的通知方法
      this.showNotification(type, message);
    },
    
    // 处理上帝选词事件
    handleGodWordSelectionEvent(event) {
      console.log('[RoomView] 收到上帝选词事件:', event.detail);
      
      // 先确保所有询问弹窗关闭
      this.showGodRoleInquiry = false;
      this.showGodRoleInquiryStatus = false;
      
      // 添加小延迟，确保前一个弹窗有时间关闭
      setTimeout(() => {
        const data = event.detail;
        
        // 判断是否是当前用户是上帝
        if (!data.god_user_id) {
          // 当前用户是上帝，显示选词弹窗
          this.showGodWordSelection = true;
          this.godWordSelectionMessage = data.message || '请选择双方词语。';
          this.godWordSelectionTimeout = data.timeout || 30;
        } else {
          // 当前用户不是上帝，显示等待状态
          this.showGodWordSelectionStatus = true;
          this.godWordSelectionStatusMessage = data.message || '正在选词。';
          this.godWordSelectionStatusTimeout = data.timeout || 30;
          this.godWordSelectionStatusUsername = data.username || '';
        }
      }, 150); // 添加150毫秒延迟
    },
    
    // 处理上帝选词完成事件
    handleGodWordsSelectedEvent(event) {
      console.log('[RoomView] 收到上帝选词完成事件:', event.detail);
      
      // 关闭所有选词相关弹窗
      this.showGodWordSelection = false;
      this.showGodWordSelectionStatus = false;
      
      // 显示游戏加载动画 - 与WebSocket消息处理保持一致
      this.showGameLoading = true;
      this.gameLoadingTitle = '游戏初始化中';
      this.gameLoadingMessage = '正在分配角色，请稍候...';
      
      // 记录调试日志
      console.log('[RoomView] 选词完成处理完毕，状态: ' +
        `选词弹窗=${this.showGodWordSelection}, ` +
        `状态弹窗=${this.showGodWordSelectionStatus}, ` + 
        `加载动画=${this.showGameLoading}`);
    },
    
    // 添加通知显示方法
    showNotification(type, message) {
      // 记录消息
      console.log(`[RoomView Notification] ${type}: ${message}`);
      
      // 创建通知元素
      const notification = document.createElement('div');
      notification.className = `room-notification ${type}`;
      notification.innerHTML = `
        <div class="notification-content">
          <span class="notification-icon">${type === 'success' ? '✅' : type === 'warning' ? '⚠️' : type === 'error' ? '❌' : 'ℹ️'}</span>
          <span class="notification-message">${message}</span>
        </div>
      `;
      
      // 添加到DOM
      document.body.appendChild(notification);
      
      // 添加进入动画
      setTimeout(() => {
        notification.classList.add('show');
      }, 10);
      
      // 设置自动移除
      setTimeout(() => {
        notification.classList.remove('show');
        notification.classList.add('hide');
        
        // 动画结束后移除元素
        setTimeout(() => {
          if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
          }
        }, 300);
      }, 5000);
    },
    // 处理上帝选词确认
    handleGodWordSelectionConfirm(wordsData) {
      console.log('[RoomView] 用户确认选词:', wordsData);
      // 发送上帝选词消息给后端
      this.websocketStore.sendMessage({
        type: 'god_words_selected',
        civilian_word: wordsData.civilian_word,
        spy_word: wordsData.spy_word
      });
      
      // 关闭选词弹窗并显示加载动画
      this.showGodWordSelection = false;
      this.showGameLoading = true;
      this.gameLoadingTitle = '游戏初始化中';
      this.gameLoadingMessage = '正在等待服务器初始化游戏...';
    },
    
    // 处理上帝选词超时
    handleGodWordSelectionTimeout() {
      console.log('[RoomView] 选词超时');
      // 实现选词超时通知后端的逻辑
      this.websocketStore.sendMessage({
        type: 'god_words_selection_timeout'
      });
      
      // 关闭选词弹窗
      this.showGodWordSelection = false;
      
      // 显示超时提示
      this.showNotification('warning', '选词超时！系统将重新询问上帝角色...');
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
  position: relative; /* 确保子元素定位相对于这个容器 */
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

/* 添加侧栏切换动画的过渡样式 */
.room-content > div {
  transition: width 0.3s ease;
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

/* 全局通知样式 */
.room-notification {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 12px 20px;
  border-radius: 8px;
  min-width: 280px;
  max-width: 400px;
  z-index: 2000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-20px);
  opacity: 0;
  transition: all 0.3s ease;
}

.room-notification.show {
  transform: translateY(0);
  opacity: 1;
}

.room-notification.hide {
  transform: translateY(-20px);
  opacity: 0;
}

.room-notification .notification-content {
  display: flex;
  align-items: center;
}

.room-notification .notification-icon {
  margin-right: 12px;
  font-size: 18px;
}

.room-notification .notification-message {
  flex: 1;
}

/* 通知类型样式 */
.room-notification.info {
  background-color: #e6f7ff;
  border-left: 5px solid #1890ff;
  color: #0050b3;
}

.room-notification.success {
  background-color: #f6ffed;
  border-left: 5px solid #52c41a;
  color: #389e0d;
}

.room-notification.warning {
  background-color: #fffbe6;
  border-left: 5px solid #faad14;
  color: #d48806;
}

.room-notification.error {
  background-color: #fff2f0;
  border-left: 5px solid #ff4d4f;
  color: #cf1322;
}
</style> 