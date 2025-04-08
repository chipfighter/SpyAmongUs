<template>
  <div class="room-page">
    <header class="room-header">
      <div class="header-left">
        <button class="back-button" @click="handleBack">
          <span class="back-icon">←</span>
        </button>
        
        <div class="room-info">
          <h1 class="room-name">{{ roomName }}</h1>
          <div class="room-meta">
            <span v-if="invitationCode" class="invitation-code">
              邀请码: {{ invitationCode }}
              <button class="copy-button" @click="copyInvitationCode">复制</button>
            </span>
          </div>
        </div>
      </div>
      
      <div class="header-right">
        <div v-if="connectionError" class="error-badge">
          连接失败
        </div>
        <button v-if="isHost" class="leave-room-button danger" @click="disbandRoom">
          解散房间
        </button>
        <button v-else class="leave-room-button" @click="leaveRoom">
          离开房间
        </button>
      </div>
    </header>

    <!-- 调试信息区域 -->
    <div class="debug-panel">
      <details>
        <summary>调试信息 (点击展开)</summary>
        <div class="debug-content">
          <p>房主ID: {{ hostId }}</p>
          <p>当前用户ID: {{ userStore.user?.id }}</p>
          <p>是否为房主: {{ isHost }}</p>
          <p>房间ID: {{ roomId }}</p>
          <p>用户列表长度: {{ roomUsers.length }}</p>
          <p>房间状态: {{ JSON.stringify(roomStore.currentRoom) }}</p>
          <p>用户列表数据: {{ JSON.stringify(roomUsers) }}</p>
        </div>
      </details>
    </div>

    <div v-if="connectionError" class="connection-error">
      <h3>网络连接错误</h3>
      <p>无法连接到服务器，请检查以下可能的原因：</p>
      <ul>
        <li>网络连接问题</li>
        <li>防火墙阻止了WebSocket连接</li>
        <li>后端服务未正确启动或已停止运行</li>
      </ul>
      <div class="error-actions">
        <button @click="retryConnection" class="retry-button">重试连接</button>
        <button @click="handleBack" class="back-button-inline">返回首页</button>
      </div>
    </div>

    <main v-if="!connectionError" class="room-content">
      <div class="chat-section">
        <Chat 
          :messages="roomMessages" 
          :roomId="roomId" 
          @send-message="handleSendMessage"
          :disabled="connectionError"
        />
      </div>
      
      <div class="users-section">
        <UserList 
          :users="roomUsers" 
          :hostId="hostId"
          :roomData="roomStore.currentRoom"
          :currentUser="userStore.user"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { userStore } from '../store/user'
import { useRoomStore } from '../store/room'
import websocketService from '../services/websocket'
import Chat from '../components/Chat.vue'
import UserList from '../components/UserList.vue'

const route = useRoute()
const router = useRouter()
const roomStore = useRoomStore()

// 获取路由参数
const roomId = computed(() => route.params.id)

// 状态和计算属性
const roomName = computed(() => roomStore.currentRoom?.name || '房间')
const hostId = computed(() => roomStore.currentRoom?.host_id || '')
const isHost = computed(() => hostId.value === userStore.user?.id)
const invitationCode = computed(() => roomStore.currentRoom?.invitation_code || '')
const roomMessages = computed(() => roomStore.getRoomMessages(roomId.value))
const roomUsers = ref([])
const connectionError = ref(false)
const isInitializing = ref(false)

// 复制邀请码
const copyInvitationCode = () => {
  navigator.clipboard.writeText(invitationCode.value)
    .then(() => {
      alert('邀请码已复制到剪贴板')
    })
    .catch(err => {
      console.error('复制失败:', err)
      alert('复制失败，请手动复制邀请码')
    })
}

// 处理发送消息
const handleSendMessage = (data) => {
  if (roomId.value) {
    if (connectionError.value) {
      // 如果连接错误，直接添加消息到本地存储
      roomStore.addMessage(roomId.value, {
        userId: userStore.user?.id,
        username: userStore.user?.username,
        content: data.content,
        timestamp: Date.now(),
        isOffline: true
      })
    } else {
      // 正常模式下发送消息
      roomStore.sendMessage(roomId.value, data.content)
    }
  }
}

// 离开房间
const leaveRoom = () => {
  if (confirm('确定要离开房间吗？')) {
    if (connectionError.value) {
      // 连接错误，直接清理数据并返回
      roomStore.clearRoomData(roomId.value)
      router.push('/')
    } else {
      // 正常模式，离开房间但不解散
      roomStore.leaveRoom(roomId.value)
      router.push('/')
    }
  }
}

// 解散房间（仅房主可操作）
const disbandRoom = () => {
  if (!isHost.value) return
  
  if (confirm('确定要解散房间吗？所有用户将被踢出房间。')) {
    if (connectionError.value) {
      // 连接错误，直接清理数据并返回
      roomStore.clearRoomData(roomId.value)
      router.push('/')
    } else {
      // 正常模式，解散房间
      roomStore.disbandRoom(roomId.value)
      router.push('/')
    }
  }
}

// 返回首页 (不解散房间，只是暂时退出)
const handleBack = () => {
  // 显示提示
  if (confirm('返回大厅不会离开当前房间，您仍然是房间成员。如需离开房间，请使用右上角的离开/解散按钮。\n\n确定返回大厅？')) {
    // 直接返回大厅但保留房间
    router.push('/')
  }
}

// 重试连接
const retryConnection = async () => {
  connectionError.value = false
  try {
    // 尝试重新连接WebSocket
    const userId = userStore.user?.id
    if (userId) {
      await websocketService.connect(userId)
      // 如果连接成功，重新初始化房间
      await initializeRoom()
    } else {
      console.error('无法重试连接：未找到用户ID')
      connectionError.value = true
    }
  } catch (error) {
    console.error('重试连接失败:', error)
    connectionError.value = true
  }
}

// 初始化函数，确保房间状态和用户列表正确设置
const initializeRoom = async () => {
  const roomId = route.params.id
  isInitializing.value = true
  console.log(`正在初始化房间: ${roomId}, 当前用户ID: ${userStore.user?.id}`)
  
  if (!roomId) {
    router.push('/home')
    console.error('房间ID未提供')
    return
  }
  
  // 获取用户信息
  const currentUserId = userStore.user?.id || localStorage.getItem('userId')
  const currentUsername = userStore.user?.username || localStorage.getItem('username')
  if (!currentUserId || !currentUsername) {
    console.error('未找到用户信息，重定向到登录页')
    router.push('/login')
    return
  }
  
  // 构建当前用户对象
  const currentUser = {
    id: currentUserId,
    username: currentUsername.trim(),
    status: '在线',
    avatar: userStore.user?.avatar || '/default_avatar.jpg'
  }
  
  // 检查WebSocket连接状态
  const isConnected = websocketService.socket?.readyState === WebSocket.OPEN
  
  // 如果WebSocket未连接，设置连接错误状态
  if (!isConnected) {
    console.error('WebSocket未连接，设置连接错误状态')
    connectionError.value = true
    isInitializing.value = false
    return
  }
  
  // 连接正常，重置错误状态
  connectionError.value = false
  
  // 检查是否已有房间信息
  if (roomStore.currentRoom?.id === roomId) {
    console.log('使用现有房间信息:', roomStore.currentRoom)
    roomName.value = roomStore.currentRoom.name
    hostId.value = roomStore.currentRoom.host_id || roomStore.currentRoom.hostId
    invitationCode.value = roomStore.currentRoom.invitation_code || roomStore.currentRoom.invitationCode
    
    // 检查当前用户是否是房主
    isHost.value = currentUserId === hostId.value
    
    console.log(`房主ID: ${hostId.value}, 当前用户ID: ${currentUserId}, 是否为房主: ${isHost.value}`)
    
    // 检查是否已有用户列表
    if (roomStore.users[roomId]?.length > 0) {
      roomUsers.value = roomStore.users[roomId]
      console.log('使用现有用户列表:', roomUsers.value)
      
      // 检查当前用户是否已在列表中
      const userExists = roomUsers.value.some(u => u.id?.trim() === currentUserId?.trim())
      
      if (!userExists) {
        console.log('当前用户不在房间列表中，添加当前用户:', currentUser)
        
        // 新增房主标识
        if (isHost.value) {
          currentUser.is_host = true
        }
        
        // 添加用户到房间
        roomStore.addUserToRoom(roomId, currentUser)
        roomUsers.value = roomStore.users[roomId]
      } else {
        console.log('当前用户已在房间列表中')
        
        // 确保用户列表响应式更新
        roomUsers.value = [...roomUsers.value]
      }
    } else {
      console.log('用户列表为空，初始化用户列表')
      
      console.log('在线模式，获取用户列表')
      
      // 异步请求用户列表
      try {
        await websocketService.sendMessage({
          type: 'get_room_users',
          data: { room_id: roomId }
        })
        console.log('已请求房间用户列表')
        
        // 等待websocket回调更新用户列表
        setTimeout(() => {
          if (!roomStore.users[roomId] || roomStore.users[roomId].length === 0) {
            console.warn('未收到服务器用户列表，添加当前用户')
            
            // 如果是房主，设置房主标识
            if (isHost.value) {
              currentUser.is_host = true
            }
            
            roomStore.addUserToRoom(roomId, currentUser)
          }
          
          roomUsers.value = roomStore.users[roomId] || []
        }, 1000)
      } catch (error) {
        console.error('获取房间用户列表失败:', error)
        connectionError.value = true
        
        // 如果获取用户列表失败，至少添加当前用户
        if (isHost.value) {
          currentUser.is_host = true
        }
        
        roomStore.addUserToRoom(roomId, currentUser)
        roomUsers.value = roomStore.users[roomId] || []
      }
    }
    
    // 初始化消息列表
    if (roomStore.messages[roomId]) {
      roomMessages.value = roomStore.messages[roomId]
    }
  } else {
    // 没有现有房间信息，初始化一个基本房间
    console.log('未找到现有房间信息，初始化基本房间')
    
    // 设置基本房间信息
    roomId.value = roomId
    roomName.value = '加载中...'
    hostId.value = route.query.host_id || '' // 尝试从URL获取房主ID
    
    // 根据URL参数判断房主
    isHost.value = (route.query.host_id === currentUserId) || 
                   (route.query.is_host === 'true') ||
                   (route.query.is_host === '1')
    
    console.log(`URL参数设置 - 房主ID: ${hostId.value}, 当前用户ID: ${currentUserId}, 是否为房主: ${isHost.value}`)
    
    // 在线模式，从服务器获取房间信息
    console.log('尝试从服务器获取房间信息')
    
    try {
      await websocketService.sendMessage({
        type: 'get_room_info',
        data: { room_id: roomId }
      })
      console.log('已请求房间信息')
      
      // 等待websocket回调更新房间信息
      setTimeout(() => {
        if (roomStore.currentRoom?.id === roomId) {
          roomName.value = roomStore.currentRoom.name
          hostId.value = roomStore.currentRoom.host_id || roomStore.currentRoom.hostId
          invitationCode.value = roomStore.currentRoom.invitation_code || roomStore.currentRoom.invitationCode
          
          // 检查当前用户是否是房主
          isHost.value = currentUserId === hostId.value
          
          console.log(`服务器返回 - 房主ID: ${hostId.value}, 当前用户ID: ${currentUserId}, 是否为房主: ${isHost.value}`)
        } else {
          console.warn('未收到服务器房间信息响应')
        }
        
        // 检查并确保当前用户在用户列表中
        addCurrentUserToRoom(roomId, currentUserId)
      }, 1000)
    } catch (error) {
      console.error('获取房间信息失败:', error)
      connectionError.value = true
      
      // 添加当前用户到用户列表
      addCurrentUserToRoom(roomId, currentUserId)
    }
  }
  
  isInitializing.value = false
}

// 添加当前用户到房间
const addCurrentUserToRoom = (roomId, userId) => {
  console.log(`确保当前用户在房间用户列表中: 房间=${roomId}, 用户ID=${userId}`)
  
  // 检查已有用户列表
  const existingUsers = roomStore.users[roomId] || []
  
  // 获取用户详细信息
  const userDetails = {
    id: userId,
    username: userStore.user?.username || localStorage.getItem('username') || '用户',
    avatar: userStore.user?.avatar || '/default_avatar.jpg',
    status: '在线'
  }
  
  // 如果是房主，设置房主标志
  if (isHost.value) {
    userDetails.is_host = true
  }
  
  // 检查用户是否已存在 (使用trim避免空格问题)
  const userExists = existingUsers.some(u => u.id?.trim() === userId?.trim())
  
  if (!userExists) {
    console.log('添加当前用户到房间:', userDetails)
    roomStore.addUserToRoom(roomId, userDetails)
    
    // 刷新用户列表
    roomUsers.value = roomStore.users[roomId] || []
  } else {
    console.log('当前用户已在房间用户列表中')
    
    // 确保列表也保持最新
    roomUsers.value = existingUsers
  }
}

// 设置WebSocket消息处理
const setupWebSocketHandlers = () => {
  console.log('设置WebSocket消息处理器')
  
  // 设置用户列表处理器
  websocketService.registerHandler('room_users', (data) => {
    console.log('收到房间用户列表:', data)
    
    if (data.room_id === route.params.id && Array.isArray(data.users)) {
      // 设置房间用户列表
      roomStore.setRoomUsers(data.room_id, data.users)
      roomUsers.value = roomStore.users[data.room_id]
      
      // 确保当前用户在列表中
      const currentUserId = userStore.user?.id || localStorage.getItem('userId')
      if (currentUserId) {
        // 使用trim避免空格问题
        const userExists = data.users.some(u => u.id?.trim() === currentUserId?.trim())
        
        if (!userExists) {
          addCurrentUserToRoom(data.room_id, currentUserId)
        }
      }
    }
  })
  
  // 处理新消息
  websocketService.onMessage('message', (data) => {
    console.log('收到聊天消息:', data)
    // 判断是否是data.data格式
    const messageData = data.data || data
    
    // 检查消息是否是当前用户发送的
    const currentUserId = userStore.user?.id
    const messageSenderId = messageData.user_id
    
    // 如果不是自己发送的消息，才添加到聊天记录
    // 自己发送的消息已经在roomStore.sendMessage中添加过
    if (messageSenderId !== currentUserId) {
      roomStore.addMessage(roomId.value, messageData)
    }
  })
  
  // 处理系统消息
  websocketService.onMessage('system_message', (data) => {
    console.log('收到系统消息:', data)
    const roomIdFromMsg = data.data?.room_id || data.room_id
    const content = data.data?.content || data.content
    
    if (roomIdFromMsg === roomId.value) {
      // 检查是否已经有类似内容的系统消息（基于内容和时间接近程度）
      const existingMessages = roomStore.getRoomMessages(roomId.value)
      const now = Date.now()
      const recentTime = now - 3000 // 3秒内
      
      // 检查最近3秒内是否已经有相同内容的系统消息
      const hasDuplicate = existingMessages.some(msg => 
        msg.type === 'system' && 
        msg.content === content && 
        msg.timestamp > recentTime
      )
      
      // 如果没有重复的系统消息，则添加
      if (!hasDuplicate) {
        roomStore.addMessage(roomId.value, {
          type: 'system',
          content: content,
          timestamp: Date.now()
        })
      } else {
        console.log('忽略重复的系统消息:', content)
      }
    }
  })
  
  // 处理消息历史
  websocketService.onMessage('message_history', (data) => {
    console.log('收到消息历史:', data)
    // 兼容两种格式
    const messages = data.data?.messages || data.messages || []
    roomStore.setMessageHistory(roomId.value, messages)
  })
  
  // 处理房间离开确认
  websocketService.onMessage('room_left', (data) => {
    console.log('收到房间离开确认:', data)
    if (data.room_id === roomId.value) {
      router.push('/')
    }
  })
  
  // 处理错误
  websocketService.onMessage('error', (data) => {
    console.error('收到WebSocket错误:', data.message)
    alert(`操作失败: ${data.message}`)
    if (data.message.includes('room')) {
      router.push('/')
    }
  })
}

// 初始化
onMounted(async () => {
  try {
    // 获取房间ID
    roomId.value = route.params.id;
    
    console.log('Room.vue组件挂载, 房间ID:', roomId.value);
    
    // 设置WebSocket消息处理
    setupWebSocketHandlers();
    
    // 检查WebSocket连接状态
    if (!websocketService.isConnected) {
      const userId = userStore.user?.id;
      if (userId) {
        try {
          await websocketService.connect(userId);
          console.log('WebSocket连接成功');
        } catch (error) {
          console.error('WebSocket连接失败:', error);
          connectionError.value = true;
        }
      } else {
        console.error('无法连接WebSocket: 用户ID不存在');
        connectionError.value = true;
      }
    }
    
    // 调用初始化函数
    await initializeRoom();
    
    // 延迟检查用户列表状态
    setTimeout(() => {
      if (roomUsers.value.length === 0 && !connectionError.value) {
        console.log('2秒后用户列表仍为空，再次尝试添加当前用户');
        addCurrentUserToRoom(roomId.value, userStore.user?.id);
      } else {
        console.log('2秒后用户列表已有内容:', roomUsers.value);
      }
    }, 2000);
  } catch (error) {
    console.error('Room组件初始化失败:', error);
    connectionError.value = true;
  }
});

// 监听房间用户列表变化
watch(() => roomStore.users[roomId.value], (newUsers) => {
  console.log('房间用户列表已更新:', newUsers);
  roomUsers.value = newUsers || [];
}, { deep: true });

// 组件销毁前清理
onBeforeUnmount(() => {
  // 离开房间
  if (roomId.value) {
    if (connectionError.value) {
      roomStore.clearRoomData(roomId.value)
    } else {
      roomStore.leaveRoom(roomId.value)
    }
  }
})
</script>

<style scoped>
.room-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
}

.room-header {
  background-color: #3f51b5;
  color: white;
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
}

.back-button {
  background: none;
  border: none;
  color: white;
  font-size: 1.5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  margin-right: 1rem;
}

.room-name {
  margin: 0;
  font-size: 1.25rem;
}

.room-meta {
  font-size: 0.85rem;
  margin-top: 0.25rem;
  opacity: 0.9;
}

.invitation-code {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.copy-button {
  background-color: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  padding: 0.15rem 0.35rem;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
}

.copy-button:hover {
  background-color: rgba(255, 255, 255, 0.3);
}

.error-badge {
  background-color: #dc3545;
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  margin-right: 0.5rem;
}

.connection-error {
  background-color: #f8d7da;
  color: #721c24;
  padding: 1.5rem;
  margin: 1rem;
  border-radius: 4px;
  border-left: 4px solid #dc3545;
  font-size: 0.9rem;
}

.connection-error h3 {
  margin-top: 0;
  margin-bottom: 0.5rem;
}

.connection-error ul {
  margin: 0.5rem 0 1rem 1.5rem;
  padding: 0;
}

.error-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.retry-button {
  background-color: #007bff;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.retry-button:hover {
  background-color: #0069d9;
}

.back-button-inline {
  background-color: #6c757d;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.back-button-inline:hover {
  background-color: #5a6268;
}

.leave-room-button {
  background-color: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.leave-room-button.danger {
  background-color: #f44336;
}

.leave-room-button:hover {
  background-color: rgba(255, 255, 255, 0.3);
}

.leave-room-button.danger:hover {
  background-color: #d32f2f;
}

.room-content {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 1.5rem;
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.chat-section, .users-section {
  height: calc(100vh - 140px);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .room-content {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
  }
  
  .chat-section {
    height: calc(100vh - 200px);
  }
  
  .users-section {
    height: auto;
    max-height: 200px;
  }
}

@media (max-width: 480px) {
  .room-header {
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-start;
  }
  
  .header-right {
    width: 100%;
  }
  
  .leave-room-button {
    width: 100%;
  }
  
  .room-content {
    padding: 1rem;
  }
  
  .chat-section {
    height: calc(100vh - 180px);
  }
}

/* 调试面板样式 */
.debug-panel {
  background-color: #f8f9fa;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin: 10px;
  padding: 5px;
  font-family: monospace;
  font-size: 12px;
}

.debug-panel summary {
  cursor: pointer;
  padding: 5px;
  font-weight: bold;
  color: #555;
}

.debug-content {
  padding: 10px;
  background-color: #fff;
  border-radius: 3px;
  overflow-x: auto;
}

.debug-content p {
  margin: 5px 0;
  word-break: break-all;
}
</style> 