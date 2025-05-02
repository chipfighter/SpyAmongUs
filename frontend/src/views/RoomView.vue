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
      :game-started="gameStarted"
      :is-god-polling="isGodPolling"
      :game-phase="roomStore.gamePhase"
      :current-round="roomStore.currentRound"
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
          :game-started="gameStarted"
          :can-speak="canSpeak"
          :current-speaker-id="currentSpeakerId"
          @send-message="handleSendMessage"
        />
      </div>
      
      <!-- 用户列表 -->
      <UserList 
        :users="roomUsers"
        :hostId="roomInfo?.host_id"
        :totalPlayers="roomInfo?.total_players"
        :currentUserId="currentUser?.id"
        :readyUsers="readyUsers"
        :gameStarted="gameStarted"
        :isReady="isReady"
        :isCollapsed="isUserListCollapsed"
        :isHost="isHost"
        :isGodPolling="isGodPolling"
        :roles="roomStore.roles"
        :currentRole="roomStore.currentRole"
        :spyTeammates="roomStore.spyTeammates"
        :currentSpeakerId="currentSpeakerId"
        :speakTimeoutSeconds="speakTimeoutSeconds"
        :currentPhase="roomStore.currentPhase"
        @toggle-collapse="handleToggleUserListCollapse"
        @toggle-ready="toggleReady"
        @toggle-secret-chat="toggleSecretChat"
        @vote="handleVote"
        @start-resize="handleStartResize"
        @add-friend="handleAddFriend"
        @view-user-details="handleViewUserDetails"
        @private-message="handlePrivateMessage"
        @kick-user="handleKickUser"
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
    
    <!-- 游戏结算弹窗 -->
    <GameResultModal
      :visible="showGameResult"
      :is-win="isGameResultWin"
      :winning-role="gameResultWinningRole"
      :current-user-id="currentUser?.id"
      :game-stats="gameResultStats"
      @close="closeGameResult"
      @prepare-next-game="prepareNextGame"
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
import GameResultModal from '@/components/Room/GameResultModal.vue'; // --- 导入结算弹窗组件 ---

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
    GameLoadingOverlay,
    GameResultModal,
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
      godWordSelectionStatusUsername: '',
      isGodPolling: false,
      // 游戏中聊天控制变量
      canSpeak: false,
      currentSpeakerId: '',
      speakingTimeout: null,
      speakTimeoutSeconds: 0,
      // 游戏结算相关数据
      showGameResult: false,
      isGameResultWin: false,
      gameResultWinningRole: '',
      gameResultStats: {
        duration: 0,
        rounds: 0,
        players: []
      },
      gameStartTimestamp: 0, // 记录游戏开始时间
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
    },
    isGodPolling() {
      return this.roomStore.isGodPolling;
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
    } else {
        // 成功获取房间详情后，建立WebSocket连接
        const token = this.userStore.accessToken;
        console.log('[RoomView] 连接WebSocket...');
        this.websocketStore.connect(roomId, token);
    }
    
    // 添加自定义事件监听器来处理上帝角色询问
    document.addEventListener('god-role-inquiry', this.handleGodRoleInquiryEvent);
    
    // 添加上帝角色询问状态事件监听器
    document.addEventListener('god-role-inquiry-status', this.handleGodRoleInquiryStatusEvent);
    
    // 添加Toast消息事件监听
    document.addEventListener('room-toast', this.handleRoomToastEvent);

    // 添加到created钩子中的事件监听:
    document.addEventListener('game-initialized', this.handleGameInitializedEvent);
  },
  mounted() {
    console.log('[RoomView] 组件挂载完成');
    
    document.addEventListener('god-role-inquiry', this.handleGodRoleInquiryEvent);
    
    document.addEventListener('god-role-inquiry-status', this.handleGodRoleInquiryStatusEvent);
    
    document.addEventListener('room-toast', this.handleRoomToastEvent);
    
    document.addEventListener('game-initialized', this.handleGameInitializedEvent);
    
    // 添加角色分配事件监听器
    document.addEventListener('role-assigned', this.handleRoleAssignedEvent);
    
    document.addEventListener('god-words-selection', this.handleGodWordSelectionEvent);
    document.addEventListener('god-words-selected', this.handleGodWordsSelectedEvent);
    
    // 添加发言轮次事件监听器
    document.addEventListener('speaking-turn', (event) => this.handleSpeakingTurn(event.detail));
    
    // 添加对立即禁言事件的监听
    document.addEventListener('immediate-disable-speaking', this.handleImmediateDisableSpeaking);
    
    // 添加投票阶段开始事件监听
    document.addEventListener('vote-phase-start', this.handleVotePhaseStart);
    
    // 监听玩家淘汰事件
    document.addEventListener('current-player-eliminated', this.handleCurrentPlayerEliminated);
    
    // 添加游戏结束结算事件监听
    document.addEventListener('game-result', this.handleGameResult);
    
    console.log('[RoomView] 事件监听器已添加');
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
    },
    // 监听游戏阶段变化
    'roomStore.gamePhase': {
      handler(newPhase, oldPhase) {
        console.log(`[RoomView Watcher] 游戏阶段变化: ${oldPhase} -> ${newPhase}`);
        
        // 如果新阶段是遗言阶段，检查当前用户是否是遗言玩家
        if (newPhase === 'last_words') {
          this.updateCanSpeakForLastWords();
        } else {
          // 不是遗言阶段，重置发言状态
          if (newPhase === 'speaking') {
            // 发言阶段，由speaking-turn事件处理
          } else {
            // 其他阶段，禁止发言
            this.canSpeak = false;
          }
        }
      }
    },
    // 监听遗言阶段发言权变化
    'roomStore.canSpeakInLastWords': {
      handler(canSpeak) {
        console.log(`[RoomView Watcher] 遗言阶段发言权变化: ${canSpeak}`);
        if (this.roomStore.gamePhase === 'last_words') {
          this.updateCanSpeakForLastWords();
        }
      }
    }
  },
  beforeUnmount() {
    console.log('[RoomView] 组件即将卸载');
    
    // 断开WebSocket连接
    if (this.websocketStore) {
      this.websocketStore.disconnect();
    }
    
    // 清理所有事件监听器
    document.removeEventListener('god-role-inquiry', this.handleGodRoleInquiryEvent);
    document.removeEventListener('god-role-inquiry-status', this.handleGodRoleInquiryStatusEvent);
    document.removeEventListener('room-toast', this.handleRoomToastEvent);
    document.removeEventListener('game-initialized', this.handleGameInitializedEvent);
    document.removeEventListener('role-assigned', this.handleRoleAssignedEvent);
    document.removeEventListener('god-words-selection', this.handleGodWordSelectionEvent);
    document.removeEventListener('god-words-selected', this.handleGodWordsSelectedEvent);
    document.removeEventListener('speaking-turn', (event) => this.handleSpeakingTurn(event.detail));
    document.removeEventListener('immediate-disable-speaking', this.handleImmediateDisableSpeaking);
    document.removeEventListener('vote-phase-start', this.handleVotePhaseStart);
    document.removeEventListener('current-player-eliminated', this.handleCurrentPlayerEliminated);
    document.removeEventListener('game-result', this.handleGameResult);
    
    console.log('[RoomView] 事件监听器已移除');
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
      if (this.gameStarted && this.canSpeak) {
        // 发送消息
        this.sendMessage();
        
        // 发送后重置发言状态
        this.canSpeak = false;
        this.currentSpeakerId = '';
        
        // 清除任何超时计时器
        if (this.speakingTimeout) {
          clearTimeout(this.speakingTimeout);
          this.speakingTimeout = null;
        }
      } else if (!this.gameStarted) {
        // 游戏未开始时正常发送消息
        this.sendMessage();
      }
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
      // 检查当前用户是否是卧底
      if (this.roomStore.currentRole !== 'spy') {
        return this.showNotification('error', '只有卧底可以使用秘密聊天');
      }
      
      // 检查当前是否是投票阶段
      if (this.roomStore.currentPhase !== 'voting') {
        return this.showNotification('error', '只能在投票阶段使用秘密聊天');
      }
      
      // 切换秘密聊天窗口
      this.showSecretChat = !this.showSecretChat;
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
      
      // 手动关闭倒计时动画
      if (this.$refs.countdownOverlay) {
        this.$refs.countdownOverlay.cancelCountdown();
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
          // 处理用户列表更新
          case 'user_list_update':
            if (data.users && Array.isArray(data.users)) {
              console.log('[RoomView] 更新用户列表:', data.users);
              this.roomStore.updateUserList(data.users);
            }
            break;
            
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
      
      // 检查当前弹窗状态并记录
      console.log('[RoomView] 弹窗状态检查 (选词完成前):', {
        showGodWordSelection: this.showGodWordSelection,
        showGodWordSelectionStatus: this.showGodWordSelectionStatus,
        showGameLoading: this.showGameLoading
      });
      
      // 强制关闭所有相关弹窗
      this.showGodRoleInquiry = false;
      this.showGodRoleInquiryStatus = false;
      this.showGodWordSelection = false;
      this.showGodWordSelectionStatus = false;
      
      // 显示游戏加载动画
      this.showGameLoading = true;
      this.gameLoadingTitle = '游戏初始化中';
      this.gameLoadingMessage = '正在等待服务器初始化游戏...';
      
      // 再次检查弹窗状态并记录
      console.log('[RoomView] 弹窗状态检查 (选词完成后):', {
        showGodWordSelection: this.showGodWordSelection,
        showGodWordSelectionStatus: this.showGodWordSelectionStatus,
        showGameLoading: this.showGameLoading
      });
    },
    
    // 添加通知显示方法
    showNotification(type, message) {
      // 跳过投票成功和玩家淘汰的提示消息
      if (message.startsWith('你已成功投票给') || message.includes('被淘汰，身份是')) {
        console.log(`[RoomView] 跳过显示通知: ${message}`);
        return;
      }
      
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
        civilian_word: wordsData.teamOne[0],
        spy_word: wordsData.teamTwo[0]
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
    // 添加处理"game-initialized"事件的方法，用于关闭加载界面
    handleGameInitializedEvent(event) {
      console.log('[RoomView] 收到游戏初始化完成事件:', event.detail);
      
      // 关闭游戏加载动画
      this.showGameLoading = false;
      
      // 初始化游戏开始时间
      this.gameStartTimestamp = Date.now();
      
      // 显示游戏开始通知
      this.showNotification('success', '游戏已初始化完成，游戏开始！');
    },
    // 处理角色分配事件
    handleRoleAssignedEvent(event) {
      console.log('[RoomView] 收到角色分配事件:', event.detail);
      
      // 获取事件详情
      const { role, civilian_word, spy_word, word } = event.detail;
      
      // 确保关闭所有相关弹窗
      this.showGodRoleInquiry = false;
      this.showGodRoleInquiryStatus = false;
      this.showGodWordSelection = false;
      this.showGodWordSelectionStatus = false;
      
      // 关闭游戏初始化动画
      this.showGameLoading = false;
      
      // 更新游戏状态
      this.gameStarted = true;
      
      // 显示通知
      let roleText = '';
      if (role === 'spy') roleText = '卧底';
      else if (role === 'civilian') roleText = '平民';
      else if (role === 'god') roleText = '上帝';
      
      // 显示角色和词语信息
      let wordText = '';
      if (role === 'spy' && (spy_word || word)) {
        wordText = `，您的词语是：${spy_word || word}`;
      } else if (role === 'civilian' && (civilian_word || word)) {
        wordText = `，您的词语是：${civilian_word || word}`;
      } else if (role === 'god') {
        wordText = '，您可以查看所有角色和词语';
      }
      
      this.showNotification('success', `您已被分配为${roleText}角色${wordText}！游戏即将开始！`);
      
      // 记录状态
      console.log('[RoomView] 角色分配后状态：', {
        游戏加载动画: this.showGameLoading,
        上帝轮询状态: this.roomStore.isGodPolling,
        游戏已开始: this.gameStarted,
        当前角色: role,
        词语信息: role === 'spy' ? (spy_word || word) : (civilian_word || word)
      });
    },
    // 处理后端广播的当前发言玩家消息
    handleSpeakingTurn(data) {
      console.log('[RoomView] 收到发言轮次消息:', data);
      
      // 清除之前的任何发言定时器
      if (this.speakingTimeout) {
        clearTimeout(this.speakingTimeout);
        this.speakingTimeout = null;
      }
      
      // 更新当前发言人ID - 使用后端提供的speaker_id字段
      this.currentSpeakerId = data.speaker_id || '';
      
      // 更新超时时间 - 使用后端提供的time_limit字段
      this.speakTimeoutSeconds = data.time_limit || 0;
      
      // 检查是否是自己的发言轮次
      const isCurrentUserTurn = this.currentSpeakerId === this.currentUser?.id;
      
      // 更新发言权限
      this.canSpeak = isCurrentUserTurn;
      
      // 如果是自己的发言轮次，自动聚焦到输入框
      if (isCurrentUserTurn && this.$refs.chatInputRef) {
        try {
          this.$refs.chatInputRef.focusInput();
        } catch (error) {
          console.error('[RoomView] 尝试聚焦输入框时出错:', error);
        }
        
        // 设置发言超时计时器（如果有时间限制）
        if (data.time_limit && data.time_limit > 0) {
          this.speakingTimeout = setTimeout(() => {
            // 如果用户没有发言，自动发送默认消息
            if (this.canSpeak && !this.newMessage.trim()) {
              this.newMessage = "我还没想好...";
              this.sendMessage();
            }
          }, data.time_limit * 1000); // 转换为毫秒
        }
      }
      
      // 通知用户轮到谁发言
      let speakerName = data.speaker_name || "未知玩家";
      if (isCurrentUserTurn) {
        speakerName = "您";
      } else if (!data.speaker_name) {
        // 如果后端没有提供speaker_name，尝试从房间用户列表中获取用户名
        const speaker = this.roomUsers.find(user => user.id === this.currentSpeakerId);
        if (speaker) {
          speakerName = speaker.username || "未知玩家";
          // 如果是AI玩家，显示AI玩家_X
          if (this.currentSpeakerId.startsWith('llm_player_')) {
            const playerNumber = this.currentSpeakerId.replace('llm_player_', '');
            speakerName = `AI玩家_${playerNumber}`;
          }
        }
      }
      
      // 显示通知
      this.showNotification('info', `当前由${speakerName}发言${this.speakTimeoutSeconds > 0 ? `，时间：${this.speakTimeoutSeconds}秒` : ''}`);
    },
    // 处理玩家投票
    handleVote(targetId) {
      console.log('[RoomView] 开始处理投票，目标玩家ID:', targetId);
      console.log('[RoomView] 当前游戏状态:', {
        gameStarted: this.roomStore.gameStarted,
        gamePhase: this.roomStore.gamePhase,
        currentUser: this.currentUser ? 
          {id: this.currentUser.id, username: this.currentUser.username} : 
          null
      });
      
      if (!this.roomStore.gameStarted || this.roomStore.gamePhase !== 'voting') {
        console.log('[RoomView] 投票失败: 当前不是投票阶段');
        return this.showNotification('error', '当前不是投票阶段');
      }
      
      if (!targetId) {
        console.log('[RoomView] 投票失败: 未选择目标玩家');
        return this.showNotification('error', '请先选择要投票的玩家');
      }
      
      // 检查玩家是否已经投过票
      if (this.roomStore.votedPlayers && this.currentUser && 
          this.roomStore.votedPlayers[this.currentUser.id] !== undefined) {
        console.log('[RoomView] 投票失败: 已经投过票了');
        return this.showNotification('warning', '您已经投过票了，每轮只能投一次票');
      }
      
      // 检查目标玩家是否已被淘汰
      const targetPlayer = this.roomUsers.find(user => user.id === targetId);
      console.log('[RoomView] 目标玩家信息:', targetPlayer ? 
        {id: targetPlayer.id, username: targetPlayer.username, eliminated: targetPlayer.eliminated} : 
        '未找到');
      
      if (targetPlayer && targetPlayer.eliminated) {
        console.log('[RoomView] 投票失败: 目标玩家已被淘汰');
        return this.showNotification('error', '该玩家已被淘汰，无法投票');
      }
      
      console.log('[RoomView] 用户投票给:', targetId);
      
      // 查找目标玩家名称用于显示
      let targetName = '未知玩家';
      if (targetPlayer) {
        targetName = targetPlayer.username || (targetPlayer.id.startsWith('llm_player_') ? 
          `AI玩家_${targetPlayer.id.replace('llm_player_', '')}` : '未知玩家');
      }
      
      // 准备要发送的投票消息
      const voteMessage = {
        type: 'vote',
        target_id: targetId
      };
      console.log('[RoomView] 准备发送投票消息:', voteMessage);
      
      // 检查websocket连接状态
      console.log('[RoomView] WebSocket连接状态:', this.websocketStore.connectionStatus);
      console.log('[RoomView] WebSocket连接是否可用:', this.websocketStore.isConnected);
      
      // 如果WebSocket连接不可用，尝试重新连接
      if (this.websocketStore.connectionStatus !== 'connected') {
        this.showNotification('warning', '网络连接不稳定，正在尝试重新连接...');
        console.log('[RoomView] 检测到WebSocket连接不可用，尝试重连');
        
        // 尝试重新连接WebSocket
        this.reconnectWebSocket().then(() => {
          console.log('[RoomView] WebSocket重连成功，重新尝试发送投票');
          // 重连成功后再次尝试发送投票消息
          this.sendVoteMessage(voteMessage, targetId, targetName);
        }).catch(error => {
          console.error('[RoomView] WebSocket重连失败:', error);
          this.showNotification('error', '网络连接失败，请刷新页面重试');
        });
        
        return;
      }
      
      // 如果WebSocket连接正常，直接发送投票消息
      this.sendVoteMessage(voteMessage, targetId, targetName);
    },
    
    // 发送投票消息的方法
    sendVoteMessage(voteMessage, targetId, targetName) {
      try {
        // 发送投票消息到后端
        const sendResult = this.websocketStore.sendMessage(voteMessage);
        console.log('[RoomView] 投票消息发送结果:', sendResult);
        
        if (!sendResult) {
          console.error('[RoomView] 投票消息发送失败');
          return this.showNotification('error', '投票失败，请检查网络连接');
        }
        
        // 预先在前端记录投票，提高响应速度
        this.roomStore.recordVote(this.currentUser.id, targetId);
        console.log('[RoomView] 前端已记录投票:', this.currentUser.id, '->', targetId);
        
        // 显示投票提交成功的动画和通知
        this.showVoteSuccessAnimation(targetId);
        
        // 显示通知
        this.showNotification('success', `你已成功投票给 ${targetName}`);
      } catch (error) {
        console.error('[RoomView] 处理投票时出错:', error);
        this.showNotification('error', `投票时发生错误: ${error.message}`);
      }
    },
    
    // 重新连接WebSocket
    async reconnectWebSocket() {
      console.log('[RoomView] 开始重连WebSocket');
      
      // 确保断开之前的连接
      this.websocketStore.disconnect(true);
      
      return new Promise((resolve, reject) => {
        // 设置超时
        const timeout = setTimeout(() => {
          reject(new Error('重连超时'));
        }, 5000);
        
        // 尝试重新连接
        this.websocketStore.connect(
          this.roomId,
          localStorage.getItem('token')
        );
        
        // 监听连接状态
        const checkConnection = setInterval(() => {
          if (this.websocketStore.connectionStatus === 'connected') {
            clearTimeout(timeout);
            clearInterval(checkConnection);
            resolve();
          }
        }, 100);
      });
    },
    
    // 显示投票成功的动画效果
    showVoteSuccessAnimation(targetId) {
      console.log('[RoomView] 显示投票成功动画，目标ID:', targetId);
      
      // 使用更可靠的方式查找目标元素，避免依赖data-user-id属性
      // 先尝试直接通过ID选择器查找 - 这更可靠
      let targetElement = document.querySelector(`.user-item[data-user-id="${targetId}"]`);
      
      // 如果找不到，则尝试通过类选择器和ID对比查找
      if (!targetElement) {
        console.log('[RoomView] 无法通过data-user-id找到元素，尝试替代方法');
        const userItems = document.querySelectorAll('.user-item');
        for (const item of userItems) {
          // 检查每个元素，看是否与目标ID匹配
          if (item.classList.contains(`user-${targetId}`)) {
            targetElement = item;
            break;
          }
        }
        
        // 如果仍然找不到，再使用更通用的方式
        if (!targetElement) {
          // 输出调试信息
          console.log(`[RoomView] 仍然无法找到元素，用户ID: ${targetId}`);
          console.log('[RoomView] 现有的用户元素：', document.querySelectorAll('.user-item').length);
          
          // 遍历所有用户元素并附加data-user-id属性以确保未来能找到
          document.querySelectorAll('.user-item').forEach(item => {
            console.log('用户元素:', item);
          });
          
          // 使用第一个用户元素作为目标
          targetElement = document.querySelector('.user-item');
          if (targetElement) {
            console.log('[RoomView] 使用第一个用户元素作为后备');
          } else {
            console.error('[RoomView] 没有找到任何用户元素，无法显示投票动画');
            return;
          }
        }
      }
      
      console.log('[RoomView] 找到目标元素:', targetElement);
      
      // 创建投票动画元素
      const voteAnimation = document.createElement('div');
      voteAnimation.className = 'vote-success-animation';
      voteAnimation.innerHTML = '✓';
      
      // 添加到目标元素
      targetElement.appendChild(voteAnimation);
      
      // 动画完成后移除元素
      setTimeout(() => {
        if (voteAnimation.parentNode) {
          voteAnimation.parentNode.removeChild(voteAnimation);
        }
        
        // 触发自定义事件清除选中状态
        document.dispatchEvent(new CustomEvent('clear-user-selection'));
      }, 1500);
    },
    // 处理立即禁言事件
    handleImmediateDisableSpeaking(event) {
      console.log('[RoomView] 收到立即禁言事件:', event.detail);
      
      // 如果是当前用户且有发言权
      if (event.detail.userId === this.currentUser?.id && this.canSpeak) {
        console.log('[RoomView] 立即禁言当前用户');
        
        // 立即禁言
        this.canSpeak = false;
        
        // 可选：通知其他人发言已结束
        this.currentSpeakerId = '';
        
        // 清除任何发言超时计时器
        if (this.speakingTimeout) {
          clearTimeout(this.speakingTimeout);
          this.speakingTimeout = null;
        }
      }
    },
    // 处理投票阶段开始的事件
    handleVotePhaseStart(data) {
      console.log('[RoomView] 投票阶段开始');
      
      // 清除发言相关状态
      this.currentSpeakerId = '';
      this.speakTimeoutSeconds = 0;
      this.canSpeak = false;
      
      // 清除任何发言计时器
      if (this.speakingTimeout) {
        clearTimeout(this.speakingTimeout);
        this.speakingTimeout = null;
      }
    },
    // 处理当前玩家被淘汰的事件
    handleCurrentPlayerEliminated(event) {
      console.log('[RoomView] 当前玩家被淘汰:', event.detail);
      
      // 显示玩家被淘汰的提示
      this.showNotification('warning', '您已被淘汰！');
      
      // 为用户提供关于遗言阶段的提示
      if (this.roomStore.gamePhase === 'last_words') {
        this.$nextTick(() => {
          this.showNotification('info', '您现在可以发表遗言，请在聊天框中输入您的遗言并发送');
          
          // 添加一个额外的视觉提示，让用户容易注意到
          // 例如闪烁聊天输入框
          const chatInput = document.querySelector('.input-container');
          if (chatInput) {
            chatInput.classList.add('highlight-input');
            setTimeout(() => {
              chatInput.classList.remove('highlight-input');
            }, 3000); // 3秒后移除高亮效果
          }
        });
      }
    },
    // 更新遗言阶段的发言状态
    updateCanSpeakForLastWords() {
      if (this.roomStore.gamePhase === 'last_words') {
        const isLastWordsPlayer = this.roomStore.lastWordsPlayerId === this.currentUser?.id;
        this.canSpeak = isLastWordsPlayer && this.roomStore.canSpeakInLastWords;
        console.log(`[RoomView] 更新遗言阶段发言状态: canSpeak=${this.canSpeak}, isLastWordsPlayer=${isLastWordsPlayer}, canSpeakInLastWords=${this.roomStore.canSpeakInLastWords}`);
      }
    },
    // 关闭游戏结算弹窗
    closeGameResult() {
      this.showGameResult = false;
    },
    
    // 准备下一局游戏
    prepareNextGame() {
      this.closeGameResult();
      this.toggleReady();
    },
    
    // 显示游戏结算弹窗
    showGameResultModal(gameEndData) {
      console.log('[RoomView] 显示游戏结算弹窗，数据:', gameEndData);
      
      // 计算游戏时长
      const gameEndTime = Date.now();
      const gameDuration = Math.floor((gameEndTime - this.gameStartTimestamp) / 1000);
      
      // 获取当前用户角色
      const currentUserRole = this.roomStore.currentRole;
      
      // 判断胜利方
      const winningRole = gameEndData.winning_role || 'civilian';
      
      // 判断当前用户是否获胜
      let isUserWin = false;
      
      if (winningRole === 'draw') {
        // 平局情况下，所有人都算获胜
        isUserWin = true;
      } else {
        // 正常胜负判断
        isUserWin = (currentUserRole === winningRole) || 
                   (currentUserRole === 'god'); // 上帝角色无胜负
      }
      
      // 准备玩家列表数据
      const playersData = [];
      
      // 添加玩家数据
      if (gameEndData.players && Array.isArray(gameEndData.players)) {
        gameEndData.players.forEach(player => {
          const playerObj = {
            id: player.id,
            name: player.username || (player.id.startsWith('llm_player_') ? 
                  `AI玩家_${player.id.replace('llm_player_', '')}` : '未知玩家'),
            role: player.role,
            avatar: player.avatar_url || '/default_avatar.jpg'
          };
          playersData.push(playerObj);
        });
      } else {
        // 如果后端没有提供玩家数据，则从当前玩家列表构建
        this.roomUsers.forEach(user => {
          const playerObj = {
            id: user.id,
            name: user.username || (user.id.startsWith('llm_player_') ? 
                  `AI玩家_${user.id.replace('llm_player_', '')}` : '未知玩家'),
            role: gameEndData.roles ? gameEndData.roles[user.id] : '',
            avatar: user.avatar_url || '/default_avatar.jpg'
          };
          playersData.push(playerObj);
        });
      }
      
      // 更新游戏结算数据
      this.isGameResultWin = isUserWin;
      this.gameResultWinningRole = winningRole;
      this.gameResultStats = {
        duration: gameDuration,
        rounds: this.roomStore.currentRound || gameEndData.rounds || 1,
        players: playersData
      };
      
      // 显示弹窗
      this.showGameResult = true;
    },
    // 处理游戏结算事件
    handleGameResult(event) {
      console.log('[RoomView] 收到游戏结算事件:', event.detail);
      
      // 显示游戏结算弹窗
      this.showGameResultModal(event.detail);
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

/* 投票成功动画样式 */
.vote-success-animation {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 40px;
  color: #4cd137;
  opacity: 0;
  animation: vote-success 1.5s ease-out forwards;
  z-index: 10;
  text-shadow: 0 0 10px rgba(76, 209, 55, 0.5);
}

@keyframes vote-success {
  0% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.5);
  }
  50% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1.2);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -50%) scale(1);
  }
}

/* 被淘汰玩家的全局样式 */
.player-eliminated {
  position: relative;
}

.player-eliminated::after {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.1);
  pointer-events: none;
  z-index: 1000;
  animation: eliminated-overlay 2s ease-in-out;
}

@keyframes eliminated-overlay {
  0% { background-color: rgba(255, 0, 0, 0.3); }
  50% { background-color: rgba(255, 0, 0, 0.1); }
  100% { background-color: rgba(0, 0, 0, 0.1); }
}

/* 遗言阶段高亮输入框 */
@keyframes lastWordsHighlight {
  0% { box-shadow: 0 0 5px rgba(255, 193, 7, 0.5); }
  50% { box-shadow: 0 0 15px rgba(255, 193, 7, 0.8); }
  100% { box-shadow: 0 0 5px rgba(255, 193, 7, 0.5); }
}

.highlight-input {
  animation: lastWordsHighlight 1.5s ease-in-out infinite;
  border: 2px solid #ffc107 !important;
}
</style> 