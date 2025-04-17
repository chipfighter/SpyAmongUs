<template>
  <div class="room-container">
    <!-- 加载状态 -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">{{ loadingText }}</div>
    </div>
    
    <!-- 顶部标题栏 -->
    <div class="room-header">
      <div class="room-title">
        <h1>{{ roomInfo.name }}</h1>
        <div class="room-code">
          邀请码: {{ roomInfo.invite_code }}
          <button class="copy-button" @click="copyInviteCode" title="复制邀请码">📋</button>
        </div>
      </div>
      <div class="connection-status" :class="connectionStatus">
        <span v-if="connectionStatus === 'connected'" title="连接正常">🟢</span>
        <span v-else-if="connectionStatus === 'connecting'" title="正在连接">🟡</span>
        <span v-else title="连接已断开">🔴</span>
      </div>
      <div class="room-actions">
        <button 
          class="back-to-lobby-button" 
          @click="backToLobby"
          title="返回大厅(保持在房间内)"
        >
          返回大厅
        </button>
        <!-- 普通用户退出按钮 -->
        <button 
          v-if="!isHost" 
          class="exit-button" 
          @click="leaveRoom"
        >
          退出房间
        </button>
        <!-- 房主专属按钮 -->
        <template v-if="isHost">
          <button 
            class="exit-button host-leave" 
            @click="leaveRoom" 
            title="退出房间并将房主移交给下一位玩家"
          >
            退出房间(移交)
          </button>
          <button 
            class="exit-button host-disband" 
            @click="disbandRoom"
            style="margin-left: 8px;"
          >
            解散房间
          </button>
        </template>
      </div>
    </div>

    <!-- 悬浮球（只在处于大厅模式时显示） -->
    <div v-if="showFloatingBall" class="floating-ball" :style="floatingBallPosition" @mousedown="startDragBall">
      <div class="ball-content">
        {{ roomInfo.name }}
      </div>
    </div>

    <!-- 简易聊天框（只在点击悬浮球后显示） -->
    <div v-if="showMiniChat" class="mini-chat">
      <div class="mini-chat-header">
        <button class="back-button" @click="returnToRoom">👈 返回房间</button>
        <h3>{{ roomInfo.name }}</h3>
      </div>
      <div class="mini-chat-messages" ref="miniChatMessages">
        <div v-for="(msg, index) in messages.slice(-10)" :key="index" class="mini-message">
          <div v-if="msg.is_system" class="mini-system-message">
            {{ msg.content }}
          </div>
          <div v-else class="mini-user-message">
            <span class="mini-username">{{ msg.username }}:</span>
            <span class="mini-content">{{ msg.content }}</span>
          </div>
        </div>
      </div>
      <div class="mini-chat-input">
        <input 
          type="text" 
          v-model="miniChatMessage" 
          @keyup.enter="sendMiniChatMessage"
          placeholder="输入消息..." 
          :disabled="connectionStatus !== 'connected'"
        />
        <button @click="sendMiniChatMessage" :disabled="connectionStatus !== 'connected' || !miniChatMessage.trim()">
          发送
        </button>
      </div>
    </div>

    <div class="room-content">
      <!-- 聊天区域 + 用户列表 -->
      <div class="chat-container">
        <!-- 消息列表 -->
        <div class="messages-container" ref="messagesContainer">
          <div v-for="(msg, index) in messages" :key="index" class="message-wrapper">
            <!-- 系统消息 -->
            <div v-if="msg.is_system" class="system-message">
              <div class="system-content">{{ msg.content }}</div>
              <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
            </div>
            
            <!-- AI流式消息 -->
            <ai-stream-message
              v-else-if="msg.type === 'ai_stream'"
              :content="msg.content"
              :is-streaming="msg.isStreaming"
              :timestamp="msg.timestamp"
            />
            
            <!-- 用户消息 -->
            <div v-else :class="['user-message', msg.user_id === currentUser.id ? 'self-message' : '']">
              <!-- 其他用户消息 (左侧) -->
              <template v-if="msg.user_id !== currentUser.id">
                <div class="avatar">
                  <img :src="getUserAvatar(msg.user_id)" alt="用户头像">
                </div>
                <div class="message-content">
                  <div class="username">{{ msg.username }}</div>
                  <div class="text" v-if="msg.parsedContent" v-html="msg.parsedContent"></div>
                  <div class="text" v-else>{{ msg.content }}</div>
                  <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
                </div>
              </template>
              
              <!-- 自己的消息 (右侧) -->
              <template v-else>
                <div class="message-content self">
                  <div class="username">{{ msg.username }}</div>
                  <div class="text" v-if="msg.parsedContent" v-html="msg.parsedContent"></div>
                  <div class="text" v-else>{{ msg.content }}</div>
                  <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
                </div>
                <div class="avatar">
                  <img :src="currentUser.avatar_url || '/default_avatar.jpg'" alt="我的头像">
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-container" @click="focusInput">
          <div class="input-wrapper">
            <textarea 
              v-model="newMessage" 
              @keydown.enter="handleEnterKey"
              @input="handleInput"
              @keydown="handleMentionNavigation"
              placeholder="输入消息..." 
              :disabled="connectionStatus !== 'connected'"
              ref="messageInput"
              class="message-textarea"
              rows="1"
            ></textarea>
            
            <!-- @用户列表弹出框 -->
            <div v-if="showMentionPopup" class="mention-popup">
              <!-- AI助手 -->
              <div 
                v-if="showAiAssistant" 
                :class="['mention-item', { 'active': selectedMentionIndex === 0 }]"
                @click="selectMention({ id: 'ai_assistant', username: 'AI助理' })"
              >
                <div class="mention-avatar">
                  <img src="/default_room_robot_avatar.jpg" alt="AI助理">
                </div>
                <div class="mention-name">AI助理</div>
              </div>
              
              <!-- 分隔线 -->
              <div v-if="showAiAssistant && filteredMentionUsers.length > 0" class="mention-divider"></div>
              
              <!-- 用户列表 -->
              <div 
                v-for="(user, index) in filteredMentionUsers" 
                :key="user.id"
                :class="['mention-item', { 'active': showAiAssistant ? index + 1 === selectedMentionIndex : index === selectedMentionIndex }]"
                @click="selectMention(user)"
              >
                <div class="mention-avatar">
                  <img :src="user.avatar_url || '/default_avatar.jpg'" alt="用户头像">
                </div>
                <div class="mention-name">{{ user.username || user.username }}</div>
              </div>
            </div>
          </div>
          <button @click="sendMessage" :disabled="connectionStatus !== 'connected' || !newMessage.trim()">
            发送
          </button>
        </div>
      </div>

      <!-- 用户列表 -->
      <div class="users-container" :class="{ 'collapsed': isUserListCollapsed }">
        <div class="resize-handle" @mousedown="startResizing"></div>
        <div class="users-header">
          <h3>玩家列表 ({{ roomUsers.length }}/{{ roomInfo.total_players || 8 }})</h3>
          <button class="collapse-btn" @click="toggleUserList">
            {{ isUserListCollapsed ? '◀' : '▶' }}
          </button>
        </div>
        
        <div class="users-list">
          <!-- 真实用户 -->
          <div v-for="user in roomUsers" :key="user.id" class="user-item">
            <div class="user-avatar">
              <img :src="user.avatar_url || '/default_avatar.jpg'" alt="用户头像">
              <span v-if="user.id === roomInfo.host_id" class="host-badge">房主</span>
            </div>
            <div class="user-name">
              {{ user.username || user.username }}
              <span v-if="readyUsers.includes(user.id)" class="ready-badge">准备</span>
            </div>
          </div>
          
          <!-- 分隔线 -->
          <div class="user-divider"></div>
          
          <!-- AI助理 -->
          <div class="user-item ai-assistant">
            <div class="user-avatar">
              <img src="/default_room_robot_avatar.jpg" alt="AI助理">
            </div>
            <div class="user-name">AI助理</div>
          </div>
        </div>
        
        <!-- 秘密聊天按钮区域 -->
        <div class="secret-chat-area">
          <button 
            v-if="gameStarted" 
            class="secret-chat-button" 
            @click="toggleSecretChat" 
            :disabled="connectionStatus !== 'connected'"
          >
            秘密聊天
          </button>
          <button 
            v-else 
            class="ready-game-button" 
            @click="toggleReady" 
            :disabled="connectionStatus !== 'connected'"
          >
            {{ isReady ? '取消准备' : '准备游戏' }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- 秘密聊天模态框 -->
    <div v-if="showSecretChat" class="secret-chat-modal">
      <div class="secret-chat-content">
        <div class="secret-chat-header">
          <h3>秘密聊天</h3>
          <button class="close-button" @click="toggleSecretChat">×</button>
        </div>
        
        <div class="secret-messages-container" ref="secretMessagesContainer">
          <div v-for="(msg, index) in secretMessages" :key="index" class="message-wrapper">
            <div :class="['user-message', msg.user_id === currentUser.id ? 'self-message' : '']">
              <!-- 其他用户消息 (左侧) -->
              <template v-if="msg.user_id !== currentUser.id">
                <div class="avatar">
                  <img :src="getUserAvatar(msg.user_id)" alt="用户头像">
                </div>
                <div class="message-content">
                  <div class="username">{{ msg.username }}</div>
                  <div class="text">{{ msg.content }}</div>
                  <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
                </div>
              </template>
              
              <!-- 自己的消息 (右侧) -->
              <template v-else>
                <div class="message-content self">
                  <div class="username">{{ msg.username }}</div>
                  <div class="text">{{ msg.content }}</div>
                  <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
                </div>
                <div class="avatar">
                  <img :src="currentUser.avatar_url || '/default_avatar.jpg'" alt="我的头像">
                </div>
              </template>
            </div>
          </div>
        </div>
        
        <!-- 选择目标用户 -->
        <div class="secret-targets">
          <div>发送给:</div>
          <div class="target-users">
            <div 
              v-for="user in secretChatTargets" 
              :key="user.id"
              class="target-user"
              :class="{ selected: selectedTargets.includes(user.id) }"
              @click="toggleTargetUser(user.id)"
            >
              {{ user.username || user.username }}
            </div>
          </div>
        </div>
        
        <!-- 输入框 -->
        <div class="input-container">
          <input 
            type="text" 
            v-model="newSecretMessage" 
            @keyup.enter="sendSecretMessage"
            placeholder="输入秘密消息..." 
            :disabled="connectionStatus !== 'connected' || selectedTargets.length === 0"
          />
          <button 
            @click="sendSecretMessage" 
            :disabled="connectionStatus !== 'connected' || selectedTargets.length === 0 || !newSecretMessage.trim()"
          >
            发送
          </button>
        </div>
      </div>
    </div>

    <!-- 错误提示模态框 -->
    <div v-if="errorModal.show" class="error-modal-overlay">
      <div class="error-modal">
        <div class="error-modal-header">
          <h3>提示</h3>
          <button class="close-button" @click="errorModal.show = false">×</button>
        </div>
        <div class="error-modal-content">
          <p>{{ errorModal.message }}</p>
        </div>
        <div class="error-modal-footer">
          <button @click="errorModal.show = false">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import AiStreamMessage from '../components/AiStreamMessage.vue'

export default {
  name: 'RoomView',
  components: {
    AiStreamMessage
  },
  data() {
    return {
      roomInfo: {
        name: '',
        invite_code: '',
        host_id: '',
        status: '',
        total_players: 8
      },
      currentUser: {
        id: '',
        username: '',
        avatar_url: ''
      },
      roomUsers: [],
      messages: [],
      secretMessages: [],
      newMessage: '',
      newSecretMessage: '',
      wsConnected: false,
      websocket: null,
      showSecretChat: false,
      selectedTargets: [],
      secretChatTargets: [],
      errorModal: {
        show: false,
        message: ''
      },
      reconnectAttempts: 0,
      isLoading: true,
      heartbeatInterval: null,
      heartbeatTimeout: null,
      connectionStatus: 'disconnected', // 'disconnected', 'connecting', 'connected'
      isComponentMounted: false,
      loadingText: '正在连接房间...',
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
      gameStarted: false,
      isReady: false,
      readyUsers: [],
      isUserListCollapsed: false,
      currentAiMessage: {
        content: '',
        isStreaming: false,
        timestamp: 0
      },
      currentAiStreamSession: null
    }
  },
  computed: {
    isHost() {
      return this.currentUser.id === this.roomInfo.host_id;
    },
    gameNotStarted() {
      return this.roomInfo.status !== 'playing';
    }
  },
  async created() {
    this.isLoading = true;
    this.isComponentMounted = true;
    
    // 获取当前用户信息
    await this.getCurrentUserInfo();
    
    // 获取路由参数中的房间ID
    const roomId = this.$route.params.roomId;
    if (!roomId) {
      this.$router.push('/lobby');
      return;
    }
    
    // 获取房间信息并初始化数据 (移除对 tempRoomData 的依赖)
    if (await this.initRoomDataFromAPI(roomId)) { // 修改调用的函数名
      // 连接WebSocket
      this.connectWebSocket();
    }
  },
  beforeUnmount() {
    console.log('组件卸载，清理资源');
    this.isComponentMounted = false;
    
    // 清除心跳检测
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
    
    // 关闭WebSocket连接
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    
    this.wsConnected = false;
    this.connectionStatus = 'disconnected';
  },
  methods: {
    async getCurrentUserInfo() {
      try {
        // 从localStorage获取用户信息或从API获取
        const userInfo = JSON.parse(localStorage.getItem('userInfo')) || {};
        this.currentUser = {
          id: userInfo.id,
          username: userInfo.username,
          avatar_url: userInfo.avatar_url
        };
      } catch (error) {
        console.error('获取用户信息失败:', error);
      }
    },
    
    // --- 重构：移除 initRoomData，改为始终从 API 获取 ---
    async initRoomDataFromAPI(roomId) {
      try {
        this.isLoading = true; // 确保开始加载
        this.loadingText = '正在加载房间信息...';
        
        // 检查localStorage中是否有缓存的活跃房间消息 (仅用于恢复消息)
        const activeRoomStr = localStorage.getItem('active_room');
        let cachedMessages = [];
        let cachedSecretMessages = [];
        
        if (activeRoomStr) {
          try {
            const activeRoomData = JSON.parse(activeRoomStr);
            if (activeRoomData.invite_code === roomId) {
              cachedMessages = activeRoomData.messages || [];
              cachedSecretMessages = activeRoomData.secretMessages || [];
              console.log('从localStorage加载的房间消息:', cachedMessages.length, '条普通消息,', cachedSecretMessages.length, '条密语');
              // 注意：这里不再加载用户列表和房间信息，只加载消息
            }
          } catch (e) {
            console.error('解析缓存的房间消息失败:', e);
          }
        }

        // 从API获取房间信息
        console.log(`正在从 API 获取房间 ${roomId} 的信息...`);
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${roomId}`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}` // 确保token名称正确
          }
        });
        
        const result = await response.json();
        console.log('API 获取房间信息响应:', result);
        
        if (result.success && result.data && result.data.room_data) {
          // 设置房间信息
          const roomData = result.data.room_data;
          this.roomInfo = {
            name: roomData.room_name,
            invite_code: roomId,
            host_id: roomData.host_id,
            status: roomData.status,
            total_players: roomData.total_players || 8
          };
          
          // 设置用户列表 (使用 API 返回的数据)
          if (roomData.users && Array.isArray(roomData.users)) {
            // 假设 API 返回的 users 已经是包含 { id, username, avatar_url } 的对象数组
            this.roomUsers = roomData.users;
            console.log('通过 API 设置初始用户列表:', this.roomUsers);
          } else {
            console.warn('API 返回的房间数据中缺少有效的 users 列表，将仅包含当前用户');
            // 如果没有users数据，至少添加当前用户
             this.roomUsers = this.roomUsers.length > 0 ? this.roomUsers : [this.currentUser]; // 保留可能已有的当前用户信息
          }
          
          // 设置可以发送秘密消息的目标
          this.secretChatTargets = this.roomUsers.filter(user => user.id !== this.currentUser.id);
          
          // 初始化消息 (优先使用缓存，否则使用 API 返回的)
           if (cachedMessages.length > 0) {
             this.messages = cachedMessages;
             console.log('已恢复', cachedMessages.length, '条缓存的消息');
           } else if (roomData.messages && Array.isArray(roomData.messages)) {
             this.messages = roomData.messages.filter(msg => msg.content && msg.content.trim() !== '');
             console.log('使用 API 返回的消息历史初始化:', this.messages.length, '条消息');
             // 可以选择性地加一条进入房间的系统消息
             if (!this.messages.some(msg => msg.is_system && msg.content.includes('进入房间'))) {
                this.messages.unshift({
                  is_system: true,
                  content: `您已进入房间 "${this.roomInfo.name}"`,
                  timestamp: Date.now()
                });
             }
           } else {
              this.messages = [{
                is_system: true,
                content: `您已进入房间 "${this.roomInfo.name}"`,
                timestamp: Date.now()
              }];
              console.log('无缓存和 API 消息历史，添加初始进入消息');
           }

           // 初始化秘密消息 (优先使用缓存，否则使用 API 返回的)
           if (cachedSecretMessages.length > 0) {
             this.secretMessages = cachedSecretMessages;
             console.log('已恢复', cachedSecretMessages.length, '条缓存的密语');
           } else {
             this.secretMessages = roomData.secret_chat_messages || [];
             console.log('使用 API 返回的密语历史初始化:', this.secretMessages.length, '条密语');
           }
          
          this.isLoading = false;
          return true; // 初始化成功
        } else {
          console.error('获取房间信息失败 (API):', result.message);
          this.showErrorModal(result.message || '房间不存在或无法加入');
          this.$router.push('/lobby');
          this.isLoading = false;
          return false; // 初始化失败
        }
      } catch (error) {
        console.error('初始化房间数据失败 (Catch):', error);
        this.showErrorModal('连接服务器失败，请刷新重试');
        this.$router.push('/lobby');
        this.isLoading = false;
        return false; // 初始化失败
      }
    },
    // --- 结束重构 ---
    
    connectWebSocket() {
      // 如果已经正在连接或已连接，不要重复连接
      if (this.connectionStatus === 'connecting' || this.connectionStatus === 'connected') {
        console.log('WebSocket已连接或正在连接，跳过连接');
        return;
      }
      
      // 从localStorage检查是否有缓存的连接状态
      const activeRoomStr = localStorage.getItem('active_room');
      let isFromLobby = false;
      
      if (activeRoomStr) {
        try {
          const activeRoom = JSON.parse(activeRoomStr);
          // 检查是否是从大厅返回的相同房间
          if (activeRoom.invite_code === this.roomInfo.invite_code) {
            isFromLobby = true;
            console.log('从大厅返回房间，当前连接状态:', activeRoom.connection_status);
            
            // 如果连接状态为已连接，跳过重新连接
            if (activeRoom.connection_status === 'connected' && this.websocket) {
              console.log('WebSocket已连接，无需重新连接');
              this.connectionStatus = 'connected';
              this.wsConnected = true;
              this.isLoading = false;
              return;
            }
          }
        } catch (e) {
          console.error('解析active_room数据失败:', e);
        }
      }
      
      // 清除active_room数据，防止下次使用过期数据
      // 只在完全连接成功后删除，确保消息历史仍然可用
      
      // 如果有旧的连接，先关闭它
      if (this.websocket) {
        try {
          // 在关闭前清除所有事件处理器
          this.websocket.onopen = null;
          this.websocket.onmessage = null;
          this.websocket.onclose = null;
          this.websocket.onerror = null;
          
          this.websocket.close();
        } catch (e) {
          console.log('关闭旧连接时出错:', e);
        }
        this.websocket = null;
      }
      
      // 清除心跳检测
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      
      // 标记为正在连接
      this.connectionStatus = 'connecting';
      this.loadingText = '正在连接房间...';
      
      // 建立WebSocket连接
      const token = localStorage.getItem('token');
      if (!token) {
        console.error('未找到用户令牌，无法连接WebSocket');
        this.connectionStatus = 'disconnected';
        this.isLoading = false;
        this.showErrorModal('未找到登录信息，请重新登录');
        return;
      }
      
      // 使用环境变量构建WebSocket URL
      const baseWsUrl = `${(import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws')}`;
      const wsUrl = `${baseWsUrl}/ws/${this.roomInfo.invite_code}?token=${token}`;
      
      console.log(`正在连接WebSocket: ${wsUrl}`);
      
      try {
        this.websocket = new WebSocket(wsUrl);
        
        // 设置连接超时
        const connectionTimeout = setTimeout(() => {
          if (this.connectionStatus === 'connecting') {
            console.log('WebSocket连接超时');
            if (this.websocket) {
              this.websocket.close();
            }
          }
        }, 10000); // 10秒连接超时
        
        this.websocket.onopen = () => {
          console.log('WebSocket连接已建立');
          clearTimeout(connectionTimeout);
          this.wsConnected = true;
          this.connectionStatus = 'connected';
          this.reconnectAttempts = 0;
          this.isLoading = false;
          
          // 成功连接后，可以清除缓存的房间数据
          if (isFromLobby) {
            console.log('从大厅返回且连接成功，更新active_room中的连接状态');
            // 不删除，而是更新连接状态
            try {
              const activeRoomStr = localStorage.getItem('active_room');
              if (activeRoomStr) {
                const activeRoom = JSON.parse(activeRoomStr);
                activeRoom.connection_status = 'connected';
                localStorage.setItem('active_room', JSON.stringify(activeRoom));
              }
            } catch (e) {
              console.error('更新active_room连接状态失败:', e);
            }
          }
          
          // 开始心跳检测
          this.startHeartbeat();
        };
        
        this.websocket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            // 处理心跳响应
            if (data.type === 'pong') {
              console.log('收到心跳响应');
              // 清除心跳超时
              if (this.heartbeatTimeout) {
                clearTimeout(this.heartbeatTimeout);
                this.heartbeatTimeout = null;
              }
              return;
            }
            
            // 处理正常消息
            console.log('收到WebSocket消息:', data);
            this.handleWebSocketMessage(data);
          } catch (error) {
            console.error('解析WebSocket消息失败:', error);
          }
        };
        
        this.websocket.onclose = (event) => {
          console.log('WebSocket连接已关闭', event);
          clearTimeout(connectionTimeout);
          this.wsConnected = false;
          
          // 清除心跳检测
          if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
          }
          
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          
          // 如果是正常关闭或不是主动关闭但超过重试次数
          if (event.code === 1000 || event.code === 1001) {
            // 正常关闭
            this.connectionStatus = 'disconnected';
            console.log('WebSocket连接已正常关闭');
            this.isLoading = false;
          } else if (this.isComponentMounted && this.connectionStatus !== 'disconnected') {
            // 非正常关闭，且组件仍然挂载，可能需要重连
            this.connectionStatus = 'disconnected';
            
            // 在有限次数内尝试重连
            if (this.reconnectAttempts < 3) {
              const delay = Math.min(3000 * Math.pow(2, this.reconnectAttempts), 10000);
              this.reconnectAttempts++;
              console.log(`连接断开，${delay/1000}秒后尝试重连 (${this.reconnectAttempts}/3)...`);
              
              setTimeout(() => {
                if (this.isComponentMounted && this.connectionStatus === 'disconnected') {
                  this.connectWebSocket();
                }
              }, delay);
            } else {
              this.isLoading = false;
              console.log('重连次数已达上限，不再尝试重连');
              this.showErrorModal('网络连接失败，请刷新页面重试');
            }
          }
        };
        
        this.websocket.onerror = (error) => {
          console.error('WebSocket连接错误:', error);
          clearTimeout(connectionTimeout);
          this.wsConnected = false;
          this.connectionStatus = 'disconnected';
        };
      } catch (error) {
        console.error('建立WebSocket连接时出错:', error);
        this.wsConnected = false;
        this.connectionStatus = 'disconnected';
        this.isLoading = false;
        this.showErrorModal('创建WebSocket连接失败，请刷新页面重试');
      }
    },
    
    startHeartbeat() {
      // 清除可能已存在的心跳检测
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      
      // 立即发送一次心跳
      this.sendHeartbeat();
      
      // 每30秒发送一次心跳
      this.heartbeatInterval = setInterval(() => {
        this.sendHeartbeat();
      }, 30000);
    },
    
    sendHeartbeat() {
      if (this.wsConnected && this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        // 发送心跳
        const pingMessage = {
          type: 'ping',
          timestamp: Date.now()
        };
        
        try {
          this.websocket.send(JSON.stringify(pingMessage));
          console.log('发送心跳');
          
          // 设置心跳超时检测
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          
          // 10秒内没有收到响应，认为连接已断开
          // ---> 修改：增加前端等待 Pong 的超时时间 <--- 
          this.heartbeatTimeout = setTimeout(() => {
            console.log('心跳超时（等待Pong超时），连接可能已断开');
            if (this.websocket) {
              // 标记连接状态为断开
              this.connectionStatus = 'disconnected';
              this.wsConnected = false;
              
              // 关闭连接
              this.websocket.close();
              this.websocket = null;
              
              // 如果组件仍然挂载，可以尝试重连
              if (this.isComponentMounted && this.reconnectAttempts < 3) {
                const delay = Math.min(3000 * Math.pow(2, this.reconnectAttempts), 10000);
                this.reconnectAttempts++;
                console.log(`心跳超时，${delay/1000}秒后尝试重连 (${this.reconnectAttempts}/3)...`);
                
                setTimeout(() => {
                  if (this.isComponentMounted && this.connectionStatus === 'disconnected') {
                    this.connectWebSocket();
                  }
                }, delay);
              } else if (this.isComponentMounted) {
                // 超过最大重试次数
                this.showErrorModal('网络连接失败，请刷新页面重试');
              }
            }
          }, 20000); // 从 10 秒增加到 20 秒
        } catch (error) {
          console.error('发送心跳失败:', error);
          // 发送失败，可能连接已断开
          this.connectionStatus = 'disconnected';
          this.wsConnected = false;
          
          if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
          }
        }
      }
    },
    
    handleWebSocketMessage(data) {
      console.log('收到WebSocket消息:', data);
      
      // 处理AI流式消息
      if (data.type === 'ai_stream') {
        // 如果是开始消息，创建新会话
        if (data.is_start) {
          // 收到开始标记，创建或重置会话ID
          this.currentAiStreamSession = data.session_id || `ai_session_fallback_${Date.now()}`;
          console.log('开始新AI流式会话:', this.currentAiStreamSession);
          
          // 创建新的AI消息对象
          const newAiMessage = {
            id: this.currentAiStreamSession,
            type: 'ai_stream',
            content: data.content || '',
            isStreaming: true,
            timestamp: data.timestamp || Date.now(),
            sessionId: this.currentAiStreamSession
          };
          
          // 添加到消息列表
          this.messages.push(newAiMessage);
        } 
        // 非开始消息，需要查找现有会话
        else {
          // 如果消息带有session_id，使用它来查找对应消息
          const sessionId = data.session_id || this.currentAiStreamSession;
          
          if (!sessionId) {
            console.error('无法处理AI流式消息：没有会话ID');
            return;
          }
          
          // 查找对应会话的消息
          const aiMessage = this.messages.find(msg => 
            msg.type === 'ai_stream' && 
            (msg.sessionId === sessionId || msg.id === sessionId)
          );
          
          if (!aiMessage) {
            console.error('找不到AI流式会话:', sessionId);
            
            // 尝试查找最后一条AI消息作为备选
            const lastAiMessage = [...this.messages].reverse().find(msg => msg.type === 'ai_stream');
            
            if (lastAiMessage) {
              // 将内容追加到最后一条AI消息
              if (data.content) {
                lastAiMessage.content += data.content;
              }
              
              // 如果是结束消息，标记流式显示结束
              if (data.is_end) {
                lastAiMessage.isStreaming = false;
                this.currentAiStreamSession = null;
              }
            } else {
              // 没有找到任何AI消息，创建一个新的
              const newAiMessage = {
                id: sessionId || `ai_session_${Date.now()}`,
                type: 'ai_stream',
                content: data.content || '',
                isStreaming: !data.is_end,
                timestamp: data.timestamp || Date.now(),
                sessionId: sessionId
              };
              
              this.messages.push(newAiMessage);
              
              if (!data.is_end) {
                this.currentAiStreamSession = sessionId;
              }
            }
            
            // 处理完毕，返回
            return;
          }
          
          // 更新现有消息
          if (data.content) {
            aiMessage.content += data.content;
          }
          
          // 如果是结束消息，标记流式显示结束
          if (data.is_end) {
                  aiMessage.isStreaming = false;
                this.currentAiStreamSession = null;
                console.log('AI流式会话结束:', aiMessage.sessionId || aiMessage.id);
          }
        }
        
        // 自动滚动到底部
        this.$nextTick(() => {
          if (this.$refs.messagesContainer) {
            this.$refs.messagesContainer.scrollTop = this.$refs.messagesContainer.scrollHeight;
          }
        });
        return;
      }
      
      // 其他类型消息的处理保持不变
      if (data.type === 'system') {
        // 处理系统消息
        if (!data.content && !data.message) return; // 避免空系统消息
        
        this.messages.push({
          is_system: true,
          content: data.content || data.message,
          timestamp: data.timestamp || Date.now()
        });
        
        // 检查是否为游戏开始消息
        if ((data.content && data.content.includes('游戏开始')) || 
            (data.message && data.message.includes('游戏开始'))) {
          this.gameStarted = true;
        }
      } else if (data.type === 'secret') {
        // 处理秘密消息
        if (!data.content || data.content.trim() === '') return; // 避免空秘密消息
        
        this.secretMessages.push(data);
      } else if (data.type === 'chat') {
        // 处理普通聊天消息
        if (!data.content || data.content.trim() === '') return; // 避免空聊天消息
        
        // 添加解析后的HTML内容
        data.parsedContent = this.parseMentions(data.content);
        this.messages.push(data);
      } else if (data.type === 'user_join' || data.type === 'user_leave') {
        // 处理用户加入/离开消息
        
        // --- 修改：直接使用 WebSocket 消息更新用户列表 ---
        if (data.user_list && Array.isArray(data.user_list)) {
          // 假设 data.user_list 包含完整的用户对象 { id, username, avatar_url }
          this.roomUsers = data.user_list; 
          // 更新秘密聊天目标（如果需要）
          this.secretChatTargets = this.roomUsers.filter(user => user.id !== this.currentUser.id);
          console.log('用户列表已通过 WebSocket 更新:', this.roomUsers);
        } else {
          // 如果消息中没有用户列表，发出警告
          console.warn(`收到的 ${data.type} 消息中缺少 user_list，用户列表可能未更新`);
          // 这里不再调用 getRoomUsers()
        }
        // --- 结束修改 ---

        // 添加系统通知
        if (data.content || data.message) {
          this.messages.push({
            is_system: true,
            content: data.content || data.message,
            timestamp: data.timestamp || Date.now()
          });
        }
      } else if (data.type === 'ready_status') {
        // 处理用户准备状态更新
        if (data.user_id && data.is_ready !== undefined) {
          const userId = data.user_id;
          const isReady = data.is_ready;
          
          if (isReady) {
            // 添加用户到准备列表
            if (!this.readyUsers.includes(userId)) {
              this.readyUsers.push(userId);
              }
            } else {
            // 从准备列表中移除用户
            const index = this.readyUsers.indexOf(userId);
            if (index !== -1) {
              this.readyUsers.splice(index, 1);
            }
          }
        }
      } else if (data.type === 'game_start') {
        // 处理游戏开始消息
        this.gameStarted = true;
        
        // 添加游戏开始系统消息
        this.messages.push({
          is_system: true,
          content: '游戏已开始',
          timestamp: data.timestamp || Date.now()
        });
      } else if (data.type === 'game_end') {
        // 处理游戏结束消息
        this.gameStarted = false;
        this.readyUsers = []; // 清空准备列表
        this.isReady = false; // 重置自己的准备状态
        
        // 添加游戏结束系统消息
        this.messages.push({
          is_system: true,
          content: '游戏已结束',
          timestamp: data.timestamp || Date.now()
        });
      } else if (data.type === 'error') {
        // 处理错误消息
        this.showErrorModal(data.content || data.message || '发生错误');
      } else if (data.type === 'host_leave') { // --- 新增：处理房主离开并移交 --- 
        // 1. 更新本地房主 ID
        if (data.new_host_id) {
          this.roomInfo.host_id = data.new_host_id;
          console.log('房主已更新为:', data.new_host_id);
        }
        
        // 2. 更新用户列表 (如果消息中包含)
        if (data.user_list && Array.isArray(data.user_list)) {
          this.roomUsers = data.user_list; 
          this.secretChatTargets = this.roomUsers.filter(user => user.id !== this.currentUser.id);
          console.log('用户列表已通过房主移交消息更新:', this.roomUsers);
        } else {
          console.warn('收到的 host_leave 消息中缺少 user_list');
        }
        
        // 3. 添加系统通知 (保留 host_leave 的系统通知)
        if (data.content || data.message) {
          this.messages.push({
            is_system: true,
            content: data.content || data.message, // 消息内容应为 "XXX退出了房间，XXX成为新房主"
            timestamp: data.timestamp || Date.now()
          });
        }
      } else {
        // 处理其他类型消息，确保有内容
        if ((data.content && data.content.trim() !== '') || 
            (data.message && data.message.trim() !== '')) {
          console.log('未知消息类型:', data.type);
          this.messages.push(data);
        }
      }
      
      // 更新localStorage中的消息历史
      this.updateCachedMessages();
      
      // 自动滚动到底部
      this.$nextTick(() => {
        if (this.$refs.messagesContainer) {
          this.$refs.messagesContainer.scrollTop = this.$refs.messagesContainer.scrollHeight;
        }
        if (this.showSecretChat && this.$refs.secretMessagesContainer) {
          this.$refs.secretMessagesContainer.scrollTop = this.$refs.secretMessagesContainer.scrollHeight;
        }
      });
    },
    
    // 更新缓存的消息历史
    updateCachedMessages() {
      // 仅保留最新的50条消息
      const activeRoomStr = localStorage.getItem('active_room');
      if (activeRoomStr) {
        try {
          const activeRoom = JSON.parse(activeRoomStr);
          // 确保是当前房间的数据
          if (activeRoom.invite_code === this.roomInfo.invite_code) {
            activeRoom.messages = this.messages.slice(-50);
            activeRoom.secretMessages = this.secretMessages.slice(-50);
            localStorage.setItem('active_room', JSON.stringify(activeRoom));
          }
        } catch (e) {
          console.error('更新缓存消息失败:', e);
        }
      }
    },
    
    sendMessage() {
      if (!this.newMessage.trim()) return;
      
      if (this.connectionStatus !== 'connected' || !this.wsConnected) {
        this.showErrorModal('网络连接已断开，请刷新页面重试');
        return;
      }
      
      // 提取消息中的所有@提及
      const mentions = [];
      const mentionRegex = /@\[([^:]+):([^\]]+)\]/g;
      let match;
      let aiType = null;
      
      while ((match = mentionRegex.exec(this.newMessage)) !== null) {
        const userId = match[1];
        const username = match[2];
        
        // 判断是否是AI助理
        if (userId === 'ai_assistant') {
          aiType = 'deepseekv3'; // 默认AI类型，后续可扩展
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
      
      // 检查消息是否包含@AI助理
      const containsAiMention = aiType !== null;
      
      const message = {
        type: 'chat',
        content: this.newMessage.trim(),
        user_id: this.currentUser.id,
        username: this.currentUser.username,
        timestamp: Date.now(),
        is_system: false,
        round: "0", // 默认回合设置为"0"
        mentions: mentions,
        ai_type: aiType,
        room_id: this.roomInfo.invite_code // 添加房间ID
      };
      
      console.log("发送消息:", JSON.stringify(message));
      
      try {
        this.websocket.send(JSON.stringify(message));
        this.newMessage = '';
      } catch (error) {
        console.error('发送消息失败:', error);
        this.showErrorModal('发送消息失败，请刷新页面重试');
        this.wsConnected = false;
        this.connectionStatus = 'disconnected';
      }
    },
    
    toggleSecretChat() {
      this.showSecretChat = !this.showSecretChat;
      if (!this.showSecretChat) {
        // 关闭窗口时清空选择和输入
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
        this.showErrorModal('网络连接已断开，请刷新页面重试');
        return;
      }
      
      const message = {
        type: 'secret',
        content: this.newSecretMessage.trim(),
        user_id: this.currentUser.id,
        username: this.currentUser.username,
        timestamp: Date.now(),
        is_system: false,
        round: "0",
        target_users: this.selectedTargets,
        room_id: this.roomInfo.invite_code
      };
      
      console.log("发送秘密消息:", JSON.stringify(message));
      
      try {
        this.websocket.send(JSON.stringify(message));
        this.newSecretMessage = '';
      } catch (error) {
        console.error('发送秘密消息失败:', error);
        this.showErrorModal('发送消息失败，请刷新页面重试');
        this.wsConnected = false;
        this.connectionStatus = 'disconnected';
      }
    },
    
    getUserAvatar(userId) {
      const user = this.roomUsers.find(u => u.id === userId);
      return user?.avatar_url || '/default_avatar.jpg';
    },
    
    showErrorModal(message) {
      this.errorModal = {
        show: true,
        message: message
      };
    },
    
    async leaveRoom() {
      // 这个方法现在统一用于"退出"操作（包括房主移交和普通用户退出）
      // 因为后端的 /leave_room API 会自动处理房主转移
      if (confirm(this.isHost ? '确定要退出并将房主移交给下一位玩家吗？' : '确定要退出房间吗？')) {
        try {
          this.isLoading = true;
          this.loadingText = '正在退出房间...';
          const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${this.roomInfo.invite_code}/leave_room`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          });
          
          const result = await response.json();
          if (result.success) {
            this.cleanupAndRedirect(); // 调用清理和跳转逻辑
            alert('已成功退出房间');
          } else {
            this.showErrorModal(`退出房间失败: ${result.message}`);
            this.isLoading = false;
          }
        } catch (error) {
          console.error('退出房间失败:', error);
          this.showErrorModal('退出房间时出错，请稍后重试');
          this.isLoading = false;
        }
      }
    },
    
    async disbandRoom() {
      // 这个方法专门用于房主解散房间
      if (!this.isHost) return; // 双重检查
      
      if (confirm('确定要解散房间吗？所有玩家将被踢出。')) {
        try {
          this.isLoading = true;
          this.loadingText = '正在解散房间...';
          // 调用解散房间API (后端应该是 delete_room)
          const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${this.roomInfo.invite_code}/delete_room`, {
            method: 'POST', // 注意：后端 API 可能是 DELETE 或 POST，需确认
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          });
          
          const result = await response.json();
          if (result.success) {
            this.cleanupAndRedirect(); // 调用清理和跳转逻辑
            alert('房间已成功解散');
          } else {
            this.showErrorModal(`解散房间失败: ${result.message}`);
            this.isLoading = false;
          }
        } catch (error) {
          console.error('解散房间失败:', error);
          this.showErrorModal('解散房间时出错，请稍后重试');
          this.isLoading = false;
        }
      }
    },

    // 提取清理 WebSocket 和重定向的逻辑
    cleanupAndRedirect() {
      console.log('正在清理WebSocket并重定向到大厅');
      this.connectionStatus = 'disconnected'; // 标记为手动断开
      if (this.websocket) {
        this.websocket.close();
        this.websocket = null;
      }
      this.wsConnected = false;
      
      // 清除心跳
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      
      // 移除活跃房间缓存，因为用户已明确离开
      localStorage.removeItem('active_room'); 
      
      this.$router.push('/lobby');
    },

    copyInviteCode() {
      // 复制邀请码到剪贴板
      navigator.clipboard.writeText(this.roomInfo.invite_code)
        .then(() => {
          alert('邀请码已复制到剪贴板！');
        })
        .catch(err => {
          console.error('复制失败:', err);
        });
    },
    
    formatTimestamp(timestamp) {
      if (!timestamp) return '';
      
      const date = new Date(timestamp);
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      });
    },
    
    // @用户相关方法
    handleInput(event) {
      const text = this.newMessage;
      const lastAtSignIndex = text.lastIndexOf('@');
      
      // 自动调整高度
      const textarea = this.$refs.messageInput;
      if (textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(150, textarea.scrollHeight) + 'px';
      }
      
      if (lastAtSignIndex !== -1) {
        const textAfterAt = text.substring(lastAtSignIndex + 1);
        // 检查@后面是否有空格或已经选择了用户（包含]字符）
        const hasCloseBracket = text.substring(lastAtSignIndex).includes(']');
        
        // 如果@后面没有空格且没有选择用户，则显示弹出框
        if (!textAfterAt.includes(' ') && !hasCloseBracket && text[lastAtSignIndex - 1] !== '@') {
          this.mentionStartIndex = lastAtSignIndex;
          this.mentionQuery = textAfterAt.trim();
          this.showMentionPopup = true;
          this.filterMentionUsers();
          this.selectedMentionIndex = 0; // 默认选中AI助手
          return;
        }
      }
      
      // 如果没有@或@后面有空格，关闭弹出框
      this.showMentionPopup = false;
    },
    
    filterMentionUsers() {
      // 过滤符合查询的用户
      const query = this.mentionQuery.toLowerCase();
      this.filteredMentionUsers = this.roomUsers.filter(user => 
        user.id !== this.currentUser.id && 
        user.username.toLowerCase().includes(query) &&
        (user.username && user.username.toLowerCase().includes(query))
      );
      
      // 是否显示AI助理
      this.showAiAssistant = 'ai助理'.includes(query) || 'ai'.includes(query) || query === '';
    },
    
    handleMentionNavigation(event) {
      // 仅在弹出框显示时处理导航键
      if (!this.showMentionPopup) return;
      
      const totalOptions = this.filteredMentionUsers.length + (this.showAiAssistant ? 1 : 0);
      if (totalOptions === 0) return;
      
      if (event.key === 'ArrowDown') {
        // 向下导航
        event.preventDefault(); // 阻止默认行为
        this.selectedMentionIndex = (this.selectedMentionIndex + 1) % totalOptions;
      } else if (event.key === 'ArrowUp') {
        // 向上导航
        event.preventDefault(); // 阻止默认行为
        this.selectedMentionIndex = (this.selectedMentionIndex - 1 + totalOptions) % totalOptions;
      } else if (event.key === 'Escape') {
        // 关闭弹出框
        event.preventDefault(); // 阻止默认行为
        this.showMentionPopup = false;
      } else if (event.key === 'Tab' && this.showMentionPopup) {
        // Tab键也可以选择
        event.preventDefault();
        if (this.showAiAssistant && this.selectedMentionIndex === 0) {
          this.selectMention({ id: 'ai_assistant', username: 'AI助理' });
        } else {
          const userIndex = this.showAiAssistant ? this.selectedMentionIndex - 1 : this.selectedMentionIndex;
          if (userIndex >= 0 && userIndex < this.filteredMentionUsers.length) {
            this.selectMention(this.filteredMentionUsers[userIndex]);
          }
        }
      }
    },
    
    selectMention(user) {
      // 选择用户后在输入框中插入@用户标记
      const beforeMention = this.newMessage.substring(0, this.mentionStartIndex);
      const afterMention = this.newMessage.substring(this.mentionStartIndex + this.mentionQuery.length + 1);
      this.newMessage = `${beforeMention}@[${user.id}:${user.username || user.username}] ${afterMention}`;
      
      // 关闭弹出框
      this.showMentionPopup = false;
      
      // 聚焦输入框
      this.$nextTick(() => {
        this.$refs.messageInput.focus();
      });
    },
    
// 处理Enter键的不同功能
handleEnterKey(event) {
  if (this.showMentionPopup) {
    // 如果显示@用户列表，Enter键用于选择用户
    event.preventDefault();
    if (this.showAiAssistant && this.selectedMentionIndex === 0) {
      this.selectMention({ id: 'ai_assistant', username: 'AI助理' });
    } else {
      const userIndex = this.showAiAssistant ? this.selectedMentionIndex - 1 : this.selectedMentionIndex;
      if (userIndex >= 0 && userIndex < this.filteredMentionUsers.length) {
        this.selectMention(this.filteredMentionUsers[userIndex]);
      }
    }
  } else {
    // Shift+Enter用于换行，普通Enter用于发送消息
    if (!event.shiftKey) {
      event.preventDefault(); // 阻止默认的换行
      this.sendMessage();
    }
    // 如果按下Shift+Enter，不做处理，textarea会自动换行
  }
},
    
    // 处理消息内容中的@标记
    parseMentions(content) {
      // 使用正则表达式匹配@[用户ID:用户名]格式
      const mentionRegex = /@\[([^:]+):([^\]]+)\]/g;
      
      // 使用HTML替换
      return content.replace(mentionRegex, (match, userId, username) => {
        const isAi = userId === 'ai_assistant';
        const mentionClass = isAi ? 'mention ai-mention' : 'mention user-mention';
        return `<span class="${mentionClass}" data-user-id="${userId}">@${username}</span>`;
      });
    },
    
    // 添加方法聚焦输入框
    focusInput() {
      if (this.$refs.messageInput && this.connectionStatus === 'connected') {
        this.$refs.messageInput.focus();
      }
    },
    
    // 返回大厅功能
    backToLobby() {
      // 保存当前状态
      this.showFloatingBall = true;
      
      // 保存房间信息和消息历史到localStorage，以便大厅页面可以使用
      const roomInfo = {
        invite_code: this.roomInfo.invite_code,
        name: this.roomInfo.name,
        position: this.floatingBallPosition,
        connection_status: this.connectionStatus,
        // 保存房主身份信息
        host_id: this.roomInfo.host_id,
        // 缓存最新的50条消息历史
        messages: this.messages.slice(-50),
        secretMessages: this.secretMessages.slice(-50)
      };
      localStorage.setItem('active_room', JSON.stringify(roomInfo));
      
      // 导航到大厅
      this.$router.push('/lobby?in_room=true');
    },
    
    // 开始拖动悬浮球
    startDragBall(event) {
      this.isDragging = true;
      const ballElement = event.currentTarget;
      const rect = ballElement.getBoundingClientRect();
      
      // 计算鼠标在悬浮球内的相对位置
      this.dragOffset = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      };
      
      // 添加鼠标移动和松开事件
      document.addEventListener('mousemove', this.dragBall);
      document.addEventListener('mouseup', this.stopDragBall);
    },
    
    // 拖动悬浮球
    dragBall(event) {
      if (!this.isDragging) return;
      
      // 计算新位置
      this.floatingBallPosition = {
        top: `${event.clientY - this.dragOffset.y}px`,
        left: `${event.clientX - this.dragOffset.x}px`
      };
    },
    
    // 停止拖动悬浮球
    stopDragBall() {
      this.isDragging = false;
      document.removeEventListener('mousemove', this.dragBall);
      document.removeEventListener('mouseup', this.stopDragBall);
      
      // 如果是点击而不是拖动，打开迷你聊天框
      if (Math.abs(this.dragOffset.x) < 5 && Math.abs(this.dragOffset.y) < 5) {
        this.showFloatingBall = false;
        this.showMiniChat = true;
      }
    },
    
    // 发送迷你聊天消息
    sendMiniChatMessage() {
      if (!this.miniChatMessage.trim()) return;
      
      // 复用现有发送消息方法
      const originalMessage = this.newMessage;
      this.newMessage = this.miniChatMessage;
      this.sendMessage();
      this.miniChatMessage = '';
      this.newMessage = originalMessage;
    },
    
    // 返回房间
    returnToRoom() {
      this.showMiniChat = false;
      this.$router.push(`/room/${this.roomInfo.invite_code}`);
    },
    
    toggleReady() {
      this.isReady = !this.isReady;
      
      // 更新本地准备状态
      if (this.isReady) {
        if (!this.readyUsers.includes(this.currentUser.id)) {
          this.readyUsers.push(this.currentUser.id);
        }
      } else {
        const index = this.readyUsers.indexOf(this.currentUser.id);
        if (index !== -1) {
          this.readyUsers.splice(index, 1);
        }
      }
    },
    
    toggleUserList() {
      this.isUserListCollapsed = !this.isUserListCollapsed;
      
      // 清除之前设置的内联样式，确保CSS类生效
      if (this.isUserListCollapsed) {
        const usersContainer = this.$el.querySelector('.users-container');
        if (usersContainer) {
          usersContainer.style.width = '';
        }
      }
    },
    
    // 处理调整宽度
    startResizing(event) {
      if (this.isUserListCollapsed) return;
      
      // 阻止事件冒泡和默认行为
      event.stopPropagation();
      event.preventDefault();
      
      // 记录初始位置
      const initialX = event.clientX;
      const initialWidth = this.$el.querySelector('.users-container').offsetWidth;
      
      // 最小和最大宽度限制
      const minWidth = 200;
      const maxWidth = 500;
      
      // 添加resizing类移除transition效果，让调整更平滑
      const usersContainer = this.$el.querySelector('.users-container');
      usersContainer.classList.add('resizing');
      
      // 鼠标移动处理函数
      const handleMouseMove = (moveEvent) => {
        // 计算拖动距离
        const deltaX = initialX - moveEvent.clientX;
        // 计算新宽度
        let newWidth = initialWidth + deltaX;
        
        // 限制最小和最大宽度
        if (newWidth < minWidth) newWidth = minWidth;
        if (newWidth > maxWidth) newWidth = maxWidth;
        
        // 应用新宽度
        usersContainer.style.width = `${newWidth}px`;
      };
      
      // 鼠标释放处理函数
      const handleMouseUp = () => {
        // 移除resizing类，恢复transition效果
        usersContainer.classList.remove('resizing');
        
        // 移除事件监听
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
      
      // 添加事件监听
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
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

.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background-color: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.room-title {
  display: flex;
  align-items: baseline;
}

.room-title h1 {
  margin: 0;
  font-size: 1.5rem;
  color: #333;
}

.room-code {
  margin-left: 15px;
  font-size: 0.9rem;
  color: #666;
  display: flex;
  align-items: center;
}

.copy-button {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  margin-left: 5px;
  padding: 3px 5px;
  border-radius: 4px;
  transition: all 0.2s;
}

.copy-button:hover {
  background-color: #f0f0f0;
  transform: scale(1.1);
}

.connection-status {
  margin-left: auto;
  margin-right: 15px;
  font-size: 1.2rem;
}

.connection-status.connected {
  color: green;
}

.connection-status.connecting {
  color: orange;
}

.connection-status.disconnected {
  color: red;
}

.exit-button {
  padding: 8px 16px;
  background-color: #eaeaea;
  border: none;
  border-radius: 4px;
  color: #333;
  cursor: pointer;
  transition: all 0.3s;
}

.exit-button:hover {
  background-color: #e0e0e0;
}

.host-exit {
  background-color: #ff4d4f;
  color: white;
}

.host-exit:hover {
  background-color: #ff7875;
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

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 10px;
  margin-bottom: 15px;
}

.message-wrapper {
  margin-bottom: 15px;
}

.system-message {
  text-align: center;
  margin: 10px 0;
}

.system-content {
  display: inline-block;
  padding: 6px 12px;
  background-color: rgba(0, 0, 0, 0.08); /* 稍微加深系统消息背景 */
  border-radius: 10px;
  color: #666; /* 稍微加深系统消息文字 */
  font-size: 13px;
}

.message-time {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.user-message {
  display: flex;
  margin: 10px 0;
  align-items: flex-start;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  margin: 0 10px;
  flex-shrink: 0;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
}

.message-content.self {
  align-items: flex-end;
}

.username {
  font-size: 12px;
  color: #666;
  margin-bottom: 2px;
}

.text {
  padding: 8px 12px;
  border-radius: 10px;
  background-color: #E3F2FD; /* 修改：稍深的浅蓝 */
  word-break: break-all;
}

.self-message {
  flex-direction: row-reverse;
}

.self-message .text {
  background-color: #3b71ca; /* 自己消息，保持不变 */
  color: white;
}

/* 新增：AI 消息气泡颜色 (假设 .text 元素有 .ai-message-bubble 类) */
.ai-message-bubble .text {
  background-color: #F5F5F5; /* 稍深的浅灰 */
  color: #333;
}

/* AI流式组件的样式 */
.ai-stream-message .text {
  background-color: #F5F5F5; /* 也应用到流式组件 */
  color: #333;
}

.input-container {
  display: flex;
  margin-top: auto;
  background-color: #fff;
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  cursor: text;
}

.input-container input {
  flex: 1;
  border: none;
  padding: 10px 15px;
  border-radius: 4px;
  outline: none;
  font-size: 1rem;
}

.input-container textarea {
  flex: 1;
  border: none;
  padding: 10px 15px;
  border-radius: 4px;
  outline: none;
  font-size: 1rem;
  resize: none !important; /* 强制禁用调整大小手柄 */
  overflow-y: auto;
  min-height: 40px;
  max-height: 150px;
  width: 100%;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.4;
}

.input-container button {
  margin-left: 10px;
  padding: 10px 20px;
  min-width: 80px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.input-container button:hover {
  background-color: #40a9ff;
}

.input-container button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.users-container {
  width: 280px;
  background-color: white;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.3s ease;
}

.users-container.resizing {
  transition: none;
}

.resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  width: 5px;
  height: 100%;
  cursor: col-resize;
  background-color: transparent;
  z-index: 10;
}

.resize-handle:hover {
  background-color: rgba(24, 144, 255, 0.1);
}

.resize-handle::before {
  content: "⬌";
  position: absolute;
  left: 5px;
  top: 50%;
  transform: translateY(-50%);
  color: #999;
  font-size: 14px;
  display: none;
}

.resize-handle:hover::before {
  display: block;
}

.users-container.collapsed {
  width: 60px;
}

.users-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.users-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
}

.users-container.collapsed .users-header h3,
.users-container.collapsed .users-list,
.users-container.collapsed .secret-chat-area {
  display: none;
}

.collapse-btn {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  padding: 5px;
  border-radius: 4px;
  transition: all 0.2s;
}

.collapse-btn:hover {
  background-color: #f0f0f0;
}

.users-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 15px;
}

.user-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f9f9f9;
}

.user-avatar {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 10px;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.host-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  background-color: #ff4d4f;
  color: white;
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 3px;
}

.user-name {
  font-size: 0.95rem;
  color: #333;
}

.user-divider {
  height: 1px;
  background-color: #e8e8e8;
  margin: 15px 0;
}

.ai-assistant .user-name {
  color: #1890ff;
}

.secret-chat-area {
  padding: 15px;
  display: flex;
  justify-content: center;
}

.secret-chat-button, .ready-game-button {
  padding: 12px 0;
  width: 100%;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s;
  text-align: center;
}

.secret-chat-button {
  background-color: #ff4d4f;
  color: white;
}

.secret-chat-button:hover {
  background-color: #ff7875;
}

.ready-game-button {
  background-color: #28a745;
  color: white;
}

.ready-game-button:hover {
  background-color: #218838;
}

.secret-chat-modal {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 350px;
  height: 450px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  z-index: 100;
}

.secret-chat-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 15px;
}

.secret-chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.secret-chat-header h3 {
  margin: 0;
  color: #722ed1;
}

.close-button {
  background: none;
  border: none;
  color: #ff4d4f;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.secret-messages-container {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 10px;
}

.secret-targets {
  margin-bottom: 10px;
}

.target-users {
  display: flex;
  flex-wrap: wrap;
  margin-top: 5px;
}

.target-user {
  background-color: #f0f0f0;
  padding: 5px 10px;
  border-radius: 15px;
  margin-right: 5px;
  margin-bottom: 5px;
  font-size: 0.85rem;
  cursor: pointer;
}

.target-user.selected {
  background-color: #722ed1;
  color: white;
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
  width: 300px;
  max-height: 80%;
  overflow-y: auto;
}

.error-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.error-modal-header h3 {
  margin: 0;
  color: #333;
}

.error-modal-content {
  margin-bottom: 10px;
}

.error-modal-footer {
  display: flex;
  justify-content: flex-end;
}

.error-modal-footer button {
  padding: 10px 20px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.error-modal-footer button:hover {
  background-color: #40a9ff;
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

.mention-popup {
  position: absolute;
  bottom: 100%;
  left: 0;
  transform: none;
  width: 200px;
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
  margin-bottom: 5px;
}

.mention-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
}

.mention-item:hover:not(.active) {
  background-color: #f5f5f5;
}

.mention-divider {
  height: 1px;
  background-color: #e8e8e8;
  margin: 4px 0;
}

.mention-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 8px;
  flex-shrink: 0;
}

.mention-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mention-name {
  font-size: 0.85rem;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mention-item.active {
  background-color: #e6f7ff;
  border-left: 3px solid #1890ff;
}

.mention {
  display: inline-block;
  padding: 0 2px;
  border-radius: 3px;
  font-weight: bold;
}

.user-mention {
  background-color: rgba(24, 144, 255, 0.1);
  color: #1890ff;
}

.ai-mention {
  background-color: rgba(114, 46, 209, 0.1);
  color: #722ed1;
}

.input-wrapper {
  position: relative;
  flex: 1;
}

.back-to-lobby-button {
  padding: 8px 16px;
  background-color: #1890ff;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  transition: all 0.3s;
  margin-right: 10px;
}

.back-to-lobby-button:hover {
  background-color: #40a9ff;
}

.floating-ball {
  position: fixed;
  width: 60px;
  height: 60px;
  background-color: #1890ff;
  border-radius: 50%;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  z-index: 1000;
  user-select: none;
}

.ball-content {
  color: white;
  font-size: 12px;
  text-align: center;
  max-width: 50px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-chat {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 300px;
  height: 400px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  z-index: 1000;
}

.mini-chat-header {
  display: flex;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
}

.mini-chat-header h3 {
  margin: 0;
  font-size: 14px;
  flex: 1;
  text-align: center;
}

.back-button {
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  color: #1890ff;
  padding: 0;
}

.mini-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.mini-message {
  margin-bottom: 8px;
  font-size: 13px;
}

.mini-system-message {
  text-align: center;
  color: #999;
  padding: 2px 0;
}

.mini-user-message {
  word-break: break-word;
}

.mini-username {
  font-weight: bold;
  margin-right: 5px;
}

.mini-chat-input {
  display: flex;
  padding: 10px;
  border-top: 1px solid #f0f0f0;
}

.mini-chat-input input {
  flex: 1;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 8px;
  outline: none;
  font-size: 13px;
}

.mini-chat-input button {
  margin-left: 8px;
  padding: 8px 12px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.mini-chat-input button:disabled {
  background-color: #ccc;
}

.ready-game-button {
  padding: 8px 16px;
  background-color: #28a745;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  transition: all 0.3s;
  margin-right: 10px;
}

.ready-game-button:hover {
  background-color: #218838;
}

.ready-badge {
  background-color: #52c41a;
  color: white;
  font-size: 0.7rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 5px;
}

/* AI流式消息相关样式 */
.ai-stream-message {
  margin: 10px 0;
}

/* 房主退出(移交)按钮样式 */
.exit-button.host-leave {
  background-color: #FFA726; /* 橙色 */
  color: white;
}

.exit-button.host-leave:hover {
  background-color: #FFB74D;
}

/* 房主解散房间按钮样式 */
.exit-button.host-disband {
  background-color: #EF5350; /* 红色 */
  color: white;
  /* margin-left: 8px;  <-- 也可以在这里加，但行内 style 更直接 */
}

.exit-button.host-disband:hover {
  background-color: #E57373;
}
</style> 