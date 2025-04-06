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
        <div v-if="isOfflineMode" class="offline-badge">
          离线模式
        </div>
        <button v-if="isHost" class="leave-room-button danger" @click="disbandRoom">
          解散房间
        </button>
        <button v-else class="leave-room-button" @click="leaveRoom">
          离开房间
        </button>
      </div>
    </header>

    <div v-if="isOfflineMode" class="offline-warning">
      注意：您正处于离线模式，无法与其他玩家交互。部分功能可能不可用。这可能是由于：
      <ul>
        <li>防火墙阻止了WebSocket连接</li>
        <li>后端服务未正确启动</li>
        <li>网络连接问题</li>
      </ul>
      建议：尝试关闭防火墙后重新登录，或检查后端服务是否正常运行。
    </div>

    <main class="room-content">
      <div class="chat-section">
        <Chat 
          :messages="roomMessages" 
          :roomId="roomId" 
          @send-message="handleSendMessage"
          :disabled="isOfflineMode && !allowOfflineChat"
        />
      </div>
      
      <div class="users-section">
        <UserList 
          :users="roomUsers" 
          :hostId="hostId"
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
const allowOfflineChat = ref(true) // 是否允许在离线模式下聊天
const isOfflineMode = computed(() => roomStore.currentRoom?.offline_mode || false)

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
    if (isOfflineMode.value) {
      // 在离线模式下，直接添加消息到本地存储
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
    if (isOfflineMode.value) {
      // 离线模式直接清理数据并返回
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
    if (isOfflineMode.value) {
      // 离线模式直接清理数据并返回
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
  // 直接返回大厅但保留房间
  router.push('/')
}

// 设置WebSocket消息处理
const setupWebSocketHandlers = () => {
  console.log('设置房间WebSocket消息处理器')
  
  // 处理新消息
  websocketService.onMessage('message', (data) => {
    console.log('收到聊天消息:', data)
    // 判断是否是data.data格式
    const messageData = data.data || data
    roomStore.addMessage(roomId.value, messageData)
  })
  
  // 处理系统消息
  websocketService.onMessage('system_message', (data) => {
    console.log('收到系统消息:', data)
    const roomIdFromMsg = data.data?.room_id || data.room_id
    const content = data.data?.content || data.content
    
    if (roomIdFromMsg === roomId.value) {
      roomStore.addMessage(roomId.value, {
        type: 'system',
        content: content,
        timestamp: Date.now()
      })
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
  // 检查用户是否登录
  if (!userStore.isLoggedIn && !localStorage.getItem('user')) {
    router.push('/login')
    return
  }
  
  // 如果是离线模式，确保用户信息从localStorage加载
  if (!userStore.user && localStorage.getItem('user')) {
    try {
      userStore.user = JSON.parse(localStorage.getItem('user'))
      userStore.loggedIn = true
    } catch (e) {
      console.error('恢复用户信息失败:', e)
      router.push('/login')
      return
    }
  }
  
  // 如果没有WebSocket连接，则建立连接（除非是离线模式）
  if (!isOfflineMode.value && !websocketService.isConnected) {
    try {
      await websocketService.connect(userStore.user?.id)
      userStore.setConnectionState?.(true)
    } catch (error) {
      console.error('WebSocket连接失败:', error)
      
      // 如果不是离线模式但连接失败，提示用户可能需要检查防火墙
      if (!isOfflineMode.value) {
        alert('网络连接失败，可能是防火墙阻止了连接。将以有限功能继续。')
      }
    }
  }
  
  // 设置WebSocket消息处理
  if (!isOfflineMode.value) {
    setupWebSocketHandlers()
  }
  
  // 如果当前没有房间信息，尝试加入房间
  if (!roomStore.currentRoom || roomStore.currentRoom.id !== roomId.value) {
    // 如果是离线模式，检查是否有保存的房间数据
    const offlineRoom = roomStore.getOfflineRoom?.(roomId.value)
    if (offlineRoom) {
      roomStore.setCurrentRoom(offlineRoom)
    } else if (!isOfflineMode.value) {
      // 加入房间时传递完整的用户信息
      await roomStore.joinRoom(roomId.value, {
        user_id: userStore.user?.id,
        username: userStore.user?.username,
        avatar: userStore.user?.avatar || ''
      })
      
      // 给WebSocket消息处理一些时间
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }
  
  // 获取当前用户信息
  const currentUser = {
    id: userStore.user?.id,
    username: userStore.user?.username,
    status: '在线',
    avatar: userStore.user?.avatar || '',
    is_host: userStore.user?.id === roomStore.currentRoom?.host_id
  }
  
  console.log('当前用户:', currentUser)
  console.log('房间信息:', roomStore.currentRoom)
  
  // 检查房间用户列表状态
  const storeUsers = roomStore.getRoomUsers(roomId.value)
  console.log('Store中的用户列表:', storeUsers)
  
  // 初始化用户列表
  if (isOfflineMode.value) {
    // 离线模式使用保存的用户
    roomUsers.value = roomStore.getRoomUsers(roomId.value) || [currentUser]
  } else {
    // 正常模式 - 确保当前用户在列表中
    const existingUsers = roomStore.getRoomUsers(roomId.value)
    
    if (existingUsers && existingUsers.length > 0) {
      // 检查当前用户是否在列表中
      const userExists = existingUsers.some(u => u.id === currentUser.id)
      if (!userExists) {
        console.log('将当前用户添加到用户列表:', currentUser)
        roomStore.addUserToRoom(roomId.value, currentUser)
      }
      roomUsers.value = roomStore.getRoomUsers(roomId.value)
    } else {
      // 如果房间为空，添加当前用户
      console.log('房间无用户，添加当前用户:', currentUser)
      roomStore.setRoomUsers(roomId.value, [currentUser])
      roomUsers.value = [currentUser]
    }
    
    // 如果当前用户是房主但不在用户列表中，确保添加
    if (isHost.value && !roomUsers.value.some(u => u.id === currentUser.id)) {
      console.log('房主不在列表中，添加房主:', currentUser)
      roomStore.addUserToRoom(roomId.value, currentUser)
      roomUsers.value = roomStore.getRoomUsers(roomId.value)
    }
    
    console.log(`房间 ${roomId.value} 用户列表已初始化:`, roomUsers.value)
  }
  
  // 如果是离线模式，添加系统消息
  if (isOfflineMode.value && roomStore.getRoomMessages(roomId.value).length === 0) {
    roomStore.addMessage(roomId.value, {
      type: 'system',
      content: '您正处于离线模式，无法与其他玩家交互。请检查网络连接或防火墙设置。',
      timestamp: Date.now()
    })
  }
})

// 组件销毁前清理
onBeforeUnmount(() => {
  // 离开房间
  if (roomId.value) {
    if (isOfflineMode.value) {
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

.offline-badge {
  background-color: #FF9800;
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  margin-right: 0.5rem;
}

.offline-warning {
  background-color: #FFF3E0;
  color: #E65100;
  padding: 1rem;
  margin: 1rem;
  border-radius: 4px;
  border-left: 4px solid #FF9800;
  font-size: 0.9rem;
}

.offline-warning ul {
  margin: 0.5rem 0 0.5rem 1.5rem;
  padding: 0;
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
</style> 