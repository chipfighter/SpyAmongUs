<template>
  <div class="home-page">
    <header class="app-header">
      <h1 class="app-title">谁是卧底</h1>
      <div class="user-info">
        <span class="username">{{ userStore.user?.username }}</span>
        <button class="logout-btn" @click="handleLogout">退出</button>
      </div>
    </header>

    <main class="main-content">
      <section class="rooms-section">
        <div class="section-header">
          <h2 class="section-title">房间列表</h2>
          <button class="refresh-btn" @click="fetchRooms" :disabled="loading">
            <span class="refresh-icon">🔄</span>
          </button>
        </div>

        <div v-if="websocketError" class="websocket-warning">
          <span class="warning-icon">⚠️</span>
          网络连接异常，可能原因：
          <ul>
            <li>防火墙阻止了WebSocket连接</li>
            <li>后端服务未正确启动或配置</li>
          </ul>
          <div class="warning-actions">
            <button @click="tryReconnect" class="reconnect-btn" :disabled="reconnecting">
              {{ reconnecting ? '重连中...' : '尝试重新连接' }}
            </button>
            <button @click="switchToOfflineMode" class="offline-btn">
              进入离线模式
            </button>
          </div>
        </div>

        <div class="rooms-container">
          <div v-if="loading" class="loading-indicator">加载中...</div>
          <div v-else-if="error" class="error-message">{{ error }}</div>
          <div v-else-if="rooms.length === 0" class="empty-message">
            暂无公开房间，创建一个吧！
          </div>
          <div v-else class="rooms-grid">
            <div 
              v-for="room in rooms" 
              :key="room.id" 
              class="room-card"
              @click="joinRoom(room.id)"
              :class="{'offline-room': room.offline_mode}"
            >
              <h3 class="room-name">{{ room.name }}</h3>
              <div class="room-info">
                <span class="user-count">{{ room.user_count || (room.users ? room.users.length : 0) }}人在线</span>
                <span v-if="room.host_id === userStore.user?.id" class="host-badge">房主</span>
                <span v-if="room.offline_mode" class="offline-badge">离线模式</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="join-create-section">
        <div class="create-room">
          <h2 class="section-title">创建房间</h2>
          <form @submit.prevent="createRoom" class="create-form">
            <div class="form-group">
              <label for="roomName">房间名称</label>
              <input 
                type="text" 
                id="roomName" 
                v-model="newRoomName" 
                placeholder="输入房间名称"
                required
                maxlength="20"
              />
            </div>
            
            <!-- 新增游戏参数设置 -->
            <div class="game-settings">
              <h3 class="settings-title">游戏设置</h3>
              
              <div class="form-group">
                <label for="playerCount">总玩家数 (3-7人)</label>
                <input 
                  type="number" 
                  id="playerCount" 
                  v-model="gameSettings.playerCount" 
                  min="3"
                  max="7"
                  required
                />
              </div>
              
              <div class="form-group">
                <label for="spyCount">卧底数量 (最少1人，最多{{Math.max(1, Math.floor(gameSettings.playerCount / 3))}}人)</label>
                <input 
                  type="number" 
                  id="spyCount" 
                  v-model="gameSettings.spyCount" 
                  min="1"
                  :max="Math.max(1, Math.floor(gameSettings.playerCount / 3))"
                  required
                />
              </div>
              
              <div class="form-group">
                <label for="maxRounds">最大回合数 (最多{{ 
                  gameSettings.playerCount > 0 && gameSettings.spyCount > 0 ? 
                  Math.min(8, (gameSettings.playerCount - gameSettings.spyCount) * 2) : 
                  8 
                }})</label>
                <input 
                  type="number" 
                  id="maxRounds" 
                  v-model="gameSettings.maxRounds" 
                  min="1"
                  :max="gameSettings.playerCount > 0 && gameSettings.spyCount > 0 ? 
                        Math.min(8, (gameSettings.playerCount - gameSettings.spyCount) * 2) : 
                        8"
                  required
                />
              </div>
              
              <div class="form-group">
                <label for="speakTime">发言时间 (秒，最多60秒)</label>
                <input 
                  type="number" 
                  id="speakTime" 
                  v-model="gameSettings.speakTime" 
                  min="10"
                  max="60"
                  required
                />
              </div>
              
              <div class="form-group">
                <label for="lastWordsTime">遗言时间 (秒，最多60秒)</label>
                <input 
                  type="number" 
                  id="lastWordsTime" 
                  v-model="gameSettings.lastWordsTime" 
                  min="10"
                  max="60"
                  required
                />
              </div>
            </div>
            
            <div class="form-group checkbox-group">
              <input type="checkbox" id="isPublic" v-model="isPublicRoom" />
              <label for="isPublic">公开房间</label>
            </div>
            <button type="submit" class="create-btn" :disabled="!newRoomName || loading">
              创建房间
            </button>
          </form>
          
          <div v-if="error" class="error-message">{{ error }}</div>
        </div>

        <div class="join-by-code">
          <h2 class="section-title">通过邀请码加入</h2>
          <form @submit.prevent="joinRoomByCode" class="join-form">
            <div class="form-group">
              <label for="inviteCode">邀请码</label>
              <input 
                type="text" 
                id="inviteCode" 
                v-model="invitationCode" 
                placeholder="输入6位邀请码"
                required
                maxlength="6"
              />
            </div>
            <button type="submit" class="join-btn" :disabled="!invitationCode || loading">
              加入房间
            </button>
          </form>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { userStore } from '../store/user'
import websocketService from '../services/websocket'
import { useRoomStore } from '../store/room'

// API基础URL常量
const API_BASE_URL = 'http://127.0.0.1:8000';

export default {
  name: 'HomeView',
  
  setup() {
    const router = useRouter()
    const roomStore = useRoomStore()
    
    // 状态
    const newRoomName = ref('')
    const isPublicRoom = ref(true)
    const invitationCode = ref('')
    const loading = ref(false)
    const error = ref('')
    const rooms = ref([])
    const currentRoom = ref(null)
    const websocketError = ref(false)
    const reconnecting = ref(false)
    
    // 游戏设置
    const gameSettings = reactive({
      playerCount: 3,
      spyCount: 1,
      maxRounds: 4,
      speakTime: 30,
      lastWordsTime: 30
    })
    
    // 初始化
    onMounted(async () => {
      console.log('Home页面加载，检查登录状态')
      
      // 检查用户是否登录
      if (!userStore.loggedIn) {
        console.log('用户未登录，重定向到登录页')
        router.push('/login')
        return
      }
      
      // 如果没有WebSocket连接，则建立连接
      if (!websocketService.isConnected) {
        try {
          console.log('尝试连接WebSocket，用户ID:', userStore.user?.id)
          await websocketService.connect(userStore.user?.id)
          console.log('WebSocket连接成功')
          websocketError.value = false
        } catch (error) {
          console.error('WebSocket连接失败:', error)
          websocketError.value = true
          console.log('提示：WebSocket连接失败可能是由于防火墙阻止。请检查防火墙设置或尝试关闭防火墙。')
        }
      }
    
      // 设置WebSocket消息处理
      setupWebSocketHandlers()
    
      // 获取公开房间列表
      fetchRooms()
    })
    
    // 清理
    onUnmounted(() => {
      // 这里可以添加一些清理逻辑
    })
    
    // 设置WebSocket消息处理器
    const setupWebSocketHandlers = () => {
      console.log('设置WebSocket消息处理器')
      
      // 处理房间创建成功
      websocketService.registerHandler('room_created', (data) => {
        console.log('房间创建成功:', data)
        const roomData = data.room || data
        currentRoom.value = roomData
        
        // 创建用户对象
        const currentUser = {
          id: userStore.user?.id,
          username: userStore.user?.username,
          status: '在线',
          is_host: userStore.user?.id === roomData.host_id
        }
        
        // 确保用户被添加到房间用户列表
        roomStore.addUserToRoom(roomData.id, currentUser)
        
        // 导航到房间页面
        router.push(`/room/${roomData.id}`)
      })
    
      // 处理房间加入成功
      websocketService.registerHandler('room_joined', (data) => {
        console.log('加入房间成功:', data)
        currentRoom.value = data
        router.push(`/room/${data.id}`)
      })
    
      // 处理公开房间列表
      websocketService.registerHandler('public_rooms', (data) => {
        console.log('收到公开房间列表:', data)
        rooms.value = data.rooms || []
        loading.value = false
      })
    
      // 处理错误
      websocketService.registerHandler('error', (data) => {
        console.error('收到WebSocket错误:', data.message)
        error.value = `操作失败: ${data.message}`
        loading.value = false
      })
    }
    
    // 获取公开房间列表
    const fetchRooms = async () => {
      loading.value = true
      error.value = ''
      
      try {
        // 检查后端服务是否可用
        const response = await fetch(`${API_BASE_URL}/`)
        
        if (!response.ok) {
          throw new Error(`服务器返回状态码: ${response.status}`)
        }
        
        console.log('后端服务正常，获取房间列表')
        
        if (websocketService.isConnected) {
          // 通过WebSocket请求房间列表
          await roomStore.fetchPublicRooms()
          rooms.value = roomStore.getPublicRooms
          // 检查是否有离线模式创建的房间
          if (roomStore.currentRoom && roomStore.currentRoom.offline_mode) {
            const offlineRoom = roomStore.currentRoom
            // 如果离线房间不在列表中，添加它
            if (!rooms.value.some(room => room.id === offlineRoom.id)) {
              rooms.value = [...rooms.value, offlineRoom]
            }
          }
        } else {
          // WebSocket未连接，检查是否有离线模式房间
          if (roomStore.currentRoom && roomStore.currentRoom.offline_mode) {
            rooms.value = [roomStore.currentRoom]
          } else {
            websocketError.value = true
            error.value = '网络连接异常，无法获取房间列表。尝试创建一个离线房间。'
          }
          loading.value = false
        }
      } catch (err) {
        console.error('获取房间列表出错:', err)
        error.value = `无法连接到服务器: ${err.message}`
        loading.value = false
        
        // 检查是否有离线模式房间
        if (roomStore.currentRoom && roomStore.currentRoom.offline_mode) {
          rooms.value = [roomStore.currentRoom]
        } else {
          websocketError.value = true
        }
      }
    }
    
    // 创建房间
    const createRoom = async () => {
      if (!newRoomName.value.trim()) return
      
      console.log('点击创建房间按钮', newRoomName.value, isPublicRoom.value, gameSettings)
      
      loading.value = true
      error.value = ''
      
      // 检查后端服务是否可访问
      try {
        const response = await fetch(`${API_BASE_URL}/`)
        
        if (!response.ok) {
          throw new Error(`服务器返回状态码: ${response.status}`)
        }
        
        console.log('后端服务正常')
        
        // 检查WebSocket连接
        if (!websocketService.isConnected) {
          const errorMsg = '网络连接异常，正在尝试重新连接...'
          console.warn(errorMsg)
          error.value = errorMsg
          
          try {
            await websocketService.connect(userStore.user?.id)
            console.log('WebSocket重新连接成功，现在创建房间')
          } catch (error) {
            const errorMsg = `无法连接到服务器: ${error.message || '未知错误'}`
            console.error(errorMsg, error)
            error.value = errorMsg
            loading.value = false
            return
          }
        }
        
        // 创建房间
        await roomStore.createRoom(
          newRoomName.value, 
          isPublicRoom.value,
          {
            player_count: gameSettings.playerCount,
            spy_count: gameSettings.spyCount,
            max_rounds: gameSettings.maxRounds,
            speak_time: gameSettings.speakTime,
            last_words_time: gameSettings.lastWordsTime
          }
        )
        
        // 创建后清空表单
        newRoomName.value = ''
      } catch (err) {
        console.error('创建房间失败:', err)
        error.value = `服务器连接失败: ${err.message}`
        loading.value = false
      }
    }
    
    // 通过ID加入房间
    const joinRoom = async (roomId) => {
      if (!roomId) return
      
      loading.value = true
      error.value = ''
      
      try {
        if (!websocketService.isConnected) {
          await websocketService.connect(userStore.user?.id)
        }
        
        await roomStore.joinRoom(roomId)
      } catch (err) {
        console.error('加入房间失败:', err)
        error.value = `加入房间失败: ${err.message}`
        loading.value = false
      }
    }
    
    // 通过邀请码加入房间
    const joinRoomByCode = async () => {
      if (!invitationCode.value.trim()) return
      
      loading.value = true
      error.value = ''
      
      try {
        if (!websocketService.isConnected) {
          await websocketService.connect(userStore.user?.id)
        }
        
        await roomStore.joinRoom(null, invitationCode.value)
        
        // 加入后清空表单
        invitationCode.value = ''
      } catch (err) {
        console.error('通过邀请码加入房间失败:', err)
        error.value = `加入房间失败: ${err.message}`
        loading.value = false
      }
    }
    
    // 登出
    const handleLogout = () => {
      userStore.logout()
    }
    
    // 尝试重新连接
    const tryReconnect = async () => {
      reconnecting.value = true
      try {
        await websocketService.connect(userStore.user?.id)
        console.log('WebSocket重新连接成功')
        websocketError.value = false
      } catch (error) {
        console.error('尝试重新连接失败:', error)
        error.value = `无法连接到服务器: ${error.message}`
        loading.value = false
      } finally {
        reconnecting.value = false
      }
    }
    
    // 切换到离线模式
    const switchToOfflineMode = () => {
      console.log('切换到离线模式')
      websocketError.value = false
    }
    
    return {
      userStore,
      newRoomName,
      isPublicRoom,
      invitationCode,
      loading,
      error,
      rooms,
      currentRoom,
      gameSettings,
      fetchRooms,
      createRoom,
      joinRoom,
      joinRoomByCode,
      handleLogout,
      websocketError,
      reconnecting,
      tryReconnect,
      switchToOfflineMode
    }
  }
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  background-color: #f5f5f5;
  padding-bottom: 50px;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: #4CAF50;
  color: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.app-title {
  font-size: 1.5rem;
  margin: 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.username {
  font-weight: 500;
}

.logout-btn {
  background-color: transparent;
  border: 1px solid white;
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background-color: white;
  color: #4CAF50;
}

.main-content {
  max-width: 1200px;
  margin: 2rem auto;
  padding: 0 1rem;
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
}

@media (min-width: 768px) {
  .main-content {
    grid-template-columns: 2fr 1fr;
  }
}

.rooms-section, .join-create-section {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-title {
  margin: 0;
  font-size: 1.25rem;
  color: #333;
}

.refresh-btn {
  background-color: transparent;
  border: none;
  cursor: pointer;
  color: #4CAF50;
  font-size: 1.25rem;
  transition: transform 0.2s;
}

.refresh-btn:hover {
  transform: rotate(45deg);
}

.refresh-btn:disabled {
  color: #ccc;
  cursor: not-allowed;
}

.rooms-container {
  min-height: 300px;
}

.rooms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
}

.room-card {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #eee;
}

.room-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
  background-color: #f0f8ff;
}

.room-name {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  color: #333;
}

.room-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: #666;
}

.host-badge {
  background-color: #4CAF50;
  color: white;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.offline-badge {
  background-color: #f44336;
  color: white;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.loading-indicator, .empty-message {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: #666;
}

.error-message {
  background-color: #ffebee;
  color: #d32f2f;
  padding: 0.75rem;
  border-radius: 4px;
  margin: 1rem 0;
}

.join-create-section {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.create-room, .join-by-code {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.game-settings {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  background-color: #f9f9f9;
}

.settings-title {
  font-size: 1rem;
  margin: 0 0 1rem 0;
  color: #555;
  border-bottom: 1px solid #ddd;
  padding-bottom: 0.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #555;
}

.form-group input[type="text"] {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.checkbox-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.checkbox-group label {
  margin: 0;
}

.create-btn, .join-btn {
  padding: 0.75rem;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.2s;
}

.create-btn {
  background-color: #4CAF50;
  color: white;
}

.create-btn:hover {
  background-color: #45a049;
}

.join-btn {
  background-color: #2196F3;
  color: white;
}

.join-btn:hover {
  background-color: #0b7dda;
}

.create-btn:disabled, .join-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.websocket-warning {
  background-color: #ffebee;
  color: #d32f2f;
  padding: 0.75rem;
  border-radius: 4px;
  margin: 1rem 0;
}

.warning-icon {
  margin-right: 0.5rem;
}

.warning-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.reconnect-btn, .offline-btn {
  background-color: transparent;
  border: none;
  cursor: pointer;
  color: #4CAF50;
  font-size: 1rem;
  transition: color 0.2s;
}

.reconnect-btn:hover, .offline-btn:hover {
  color: #45a049;
}
</style> 