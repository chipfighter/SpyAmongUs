<template>
  <div class="lobby-container">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="action-buttons">
        <button class="create-room-btn" @click="showCreateRoomDialog = true">
          <i class="icon">+</i> 创建房间
        </button>
        <button class="join-room-btn">
          <i class="icon">→</i> 加入房间
        </button>
      </div>
      
      <div class="logo">谁是卧底</div>
      
      <div class="user-info">
        <span class="username">{{ userStore.user?.username || '未登录' }}</span>
        <div class="avatar-container">
          <img :src="userStore.userAvatar" alt="用户头像" class="avatar" />
        </div>
        <button @click="handleLogout" class="logout-btn" title="登出">
          退出
        </button>
      </div>
    </header>
    
    <!-- 大厅内容区 -->
    <main class="lobby-content">
      <div class="section-header">
        <h2 class="section-title">游戏大厅</h2>
        <button class="refresh-btn" title="刷新房间列表" @click="refreshRooms">
          <span class="refresh-icon">↻</span>
        </button>
      </div>
      
      <!-- 空状态 -->
      <div class="empty-state" v-if="publicRooms.length === 0">
        <div class="empty-icon">🏠</div>
        <h3>暂无公开房间</h3>
        <p>点击顶部按钮创建或加入房间</p>
      </div>
      
      <!-- 房间列表 - 当有房间时会显示 -->
      <div class="room-list" v-if="publicRooms.length > 0">
        <div class="room-card" v-for="room in publicRooms" :key="room.invite_code">
          <div class="room-header">
            <h3 class="room-name">{{ room.room_name }}</h3>
            <span class="room-status">{{ room.status === 'waiting' ? '等待中' : '游戏中' }}</span>
          </div>
          <div class="room-info">
            <div class="room-host">房主: {{ room.host_name }}</div>
            <div class="room-players">{{ room.current_players }}/{{ room.total_players }} 人</div>
          </div>
          <button class="join-room-card-btn" @click="joinRoom(room.invite_code)" :disabled="room.status !== 'waiting'">
            {{ room.status === 'waiting' ? '加入房间' : '游戏中' }}
          </button>
        </div>
      </div>
    </main>
    
    <!-- 创建房间弹窗 -->
    <div class="dialog-overlay" v-if="showCreateRoomDialog" @click.self="showCreateRoomDialog = false">
      <div class="create-room-dialog">
        <div class="dialog-header">
          <h2>创建新房间</h2>
          <button class="close-btn" @click="showCreateRoomDialog = false">×</button>
        </div>
        
        <div class="dialog-body">
          <!-- 错误提示 -->
          <div class="error-message" v-if="formError">
            {{ formError }}
          </div>
          
          <div class="form-group">
            <label>房间名称</label>
            <input v-model="roomData.room_name" type="text" placeholder="输入房间名称" class="input-control">
          </div>
          
          <div class="form-group">
            <label>是否公开</label>
            <div class="toggle-switch">
              <label class="switch">
                <input type="checkbox" v-model="roomData.is_public">
                <span class="slider round"></span>
              </label>
              <span class="toggle-label">{{ roomData.is_public ? '公开' : '私密' }}</span>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>总玩家数 <span class="help-text">(3-8人)</span></label>
              <input v-model.number="roomData.total_players" type="number" min="3" max="8" class="input-control">
            </div>
            
            <div class="form-group">
              <label>卧底数量 <span class="help-text">(1-3人)</span></label>
              <input v-model.number="roomData.spy_count" type="number" min="1" max="3" class="input-control">
            </div>
          </div>
          
          <div class="form-group">
            <label>最大回合数 <span class="help-text">(基础回合数：总人数-卧底数；最大回合数：≤10)</span></label>
            <input v-model.number="roomData.max_rounds" type="number" min="1" max="10" class="input-control">
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>发言时间 <span class="help-text">(≤60秒)</span></label>
              <input v-model.number="roomData.speak_time" type="number" min="30" max="60" class="input-control">
            </div>
            
            <div class="form-group">
              <label>遗言时间 <span class="help-text">(≤60秒)</span></label>
              <input v-model.number="roomData.last_words_time" type="number" min="30" max="60" class="input-control">
            </div>
          </div>
          
          <div class="form-group">
            <label>大模型自由聊天（当前版本不支持）</label>
            <div class="toggle-switch">
              <label class="switch">
                <input type="checkbox" v-model="roomData.llm_free">
                <span class="slider round"></span>
              </label>
              <span class="toggle-label">{{ roomData.llm_free ? '允许' : '不允许' }}</span>
            </div>
          </div>
        </div>
        
        <div class="dialog-footer">
          <button class="cancel-btn" @click="showCreateRoomDialog = false">取消</button>
          <button class="create-btn" @click="validateAndCreateRoom">确认创建</button>
        </div>
      </div>
    </div>

    <!-- 悬浮球（从房间返回时显示） -->
    <div v-if="showFloatingBall && activeRoom" class="floating-ball" :style="floatingBallPosition" @mousedown="startDragBall">
      <div class="ball-content">
        {{ activeRoom.name }}
      </div>
    </div>

    <!-- 简易聊天框（只在点击悬浮球后显示） -->
    <div v-if="showMiniChat && activeRoom" class="mini-chat">
      <div class="mini-chat-header">
        <button class="back-button" @click="returnToRoom">👈 返回房间</button>
        <h3>{{ activeRoom.name }}</h3>
        <button class="close-chat-button" @click="closeMiniChat">×</button>
      </div>
      <div class="mini-chat-content">
        <div class="mini-message system-message">
          请返回房间继续聊天
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/userStore'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 创建房间相关
const showCreateRoomDialog = ref(false)
const formError = ref('')
const roomData = ref({
  room_name: '',
  is_public: true,
  total_players: 5,
  spy_count: 1,
  max_rounds: 10,
  speak_time: 60,
  last_words_time: 60,
  llm_free: false
})

// 房间列表相关
const publicRooms = ref([])
const isLoading = ref(false)

// 悬浮球相关
const showFloatingBall = ref(false)
const showMiniChat = ref(false)
const activeRoom = ref(null)
const floatingBallPosition = ref({
  top: '100px',
  left: '20px'
})
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

onMounted(() => {
  // 初始化用户数据
  userStore.initStore()
  
  // 如果没有登录则跳转到登录页
  if (!userStore.isAuthenticated) {
    router.push('/login')
  } else {
    // 加载公开房间列表
    refreshRooms()
    
    // 检查是否有活动房间并显示悬浮球
    checkActiveRoom()
  }
})

onBeforeUnmount(() => {
  // 移除可能添加的事件监听器
  document.removeEventListener('mousemove', dragBall)
  document.removeEventListener('mouseup', stopDragBall)
})

async function refreshRooms() {
  isLoading.value = true
  try {
    // 调用API获取公开房间列表
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/rooms/refresh_public_room`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    if (response.ok) {
      const result = await response.json();
      if (result.success && result.data && result.data.rooms) {
        publicRooms.value = result.data.rooms;
      } else {
        publicRooms.value = [];
      }
    } else {
      console.error('刷新房间列表失败');
      publicRooms.value = [];
    }
  } catch (error) {
    console.error('获取房间列表失败:', error)
    publicRooms.value = []
  } finally {
    isLoading.value = false
  }
}

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}

function validateAndCreateRoom() {
  // 清除之前的错误信息
  formError.value = ''
  
  // 验证房间名称
  if (!roomData.value.room_name.trim()) {
    formError.value = '请输入房间名称'
    return
  }
  
  // 验证总玩家数
  if (roomData.value.total_players < 3 || roomData.value.total_players > 8) {
    formError.value = '总玩家数必须在3-8人之间'
    return
  }
  
  // 验证卧底数量
  if (roomData.value.spy_count < 1 || roomData.value.spy_count > 3) {
    formError.value = '卧底数量必须在1-3人之间'
    return
  }
  
  // 验证卧底数量不能超过总玩家数的一半
  if (roomData.value.spy_count > Math.floor(roomData.value.total_players / 2)) {
    formError.value = '卧底数量不能超过总玩家数的一半'
    return
  }
  
  // 验证最大回合数
  const minRounds = roomData.value.total_players - roomData.value.spy_count
  if (roomData.value.max_rounds < minRounds) {
    formError.value = `最大回合数不能小于基础回合数: ${minRounds}`
    return
  }
  
  if (roomData.value.max_rounds > 10) {
    formError.value = '最大回合数不能超过10'
    return
  }
  
  // 验证发言时间
  if (roomData.value.speak_time < 30 || roomData.value.speak_time > 60) {
    formError.value = '发言时间必须在30-60秒之间'
    return
  }
  
  // 验证遗言时间
  if (roomData.value.last_words_time < 30 || roomData.value.last_words_time > 60) {
    formError.value = '遗言时间必须在30-60秒之间'
    return
  }
  
  // 如果验证通过，则创建房间
  createRoom()
}

async function createRoom() {
  try {
    formError.value = ''
    isLoading.value = true
    
    // 调用创建房间API
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify(roomData.value)
    })
    
    const result = await response.json()
    
    if (result.success) {
      console.log('房间创建成功:', result)
      // 关闭对话框
      showCreateRoomDialog.value = false
      
      // 获取房间数据
      const inviteCode = result.data.invite_code
      
      // 将完整的返回结果暂存在localStorage中
      localStorage.setItem('tempRoomData', JSON.stringify(result))
      
      // 跳转到房间页面
      router.push(`/room/${inviteCode}`)
    } else {
      // 显示错误信息
      formError.value = result.message || '创建房间失败'
    }
  } catch (error) {
    console.error('创建房间出错:', error)
    formError.value = '创建房间时出错，请稍后再试'
  } finally {
    isLoading.value = false
  }
}

async function joinRoom(inviteCode) {
  try {
    isLoading.value = true
    
    // 调用加入房间API
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${inviteCode}/join`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    
    const result = await response.json()
    
    if (result.success) {
      // 保存完整的返回结果
      localStorage.setItem('tempRoomData', JSON.stringify(result))
      
      // 加入成功，跳转到房间
      router.push(`/room/${inviteCode}`)
    } else {
      // 显示加入失败提示
      alert(result.message || '加入房间失败')
    }
  } catch (error) {
    console.error('加入房间出错:', error)
    alert('加入房间时出错，请稍后再试')
  } finally {
    isLoading.value = false
  }
}

function checkActiveRoom() {
  // 检查URL参数中是否有in_room=true
  const inRoom = route.query.in_room === 'true'
  
  // 从localStorage获取活动房间信息
  const roomData = localStorage.getItem('active_room')
  
  if (inRoom && roomData) {
    try {
      // 解析房间数据
      activeRoom.value = JSON.parse(roomData)
      
      // 设置悬浮球位置
      if (activeRoom.value.position) {
        floatingBallPosition.value = activeRoom.value.position
      }
      
      // 显示悬浮球
      showFloatingBall.value = true
    } catch (error) {
      console.error('解析房间数据失败:', error)
    }
  }
}

// 开始拖动悬浮球
function startDragBall(event) {
  isDragging.value = true
  const ballElement = event.currentTarget
  const rect = ballElement.getBoundingClientRect()
  
  // 计算鼠标在悬浮球内的相对位置
  dragOffset.value = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  }
  
  // 添加鼠标移动和松开事件
  document.addEventListener('mousemove', dragBall)
  document.addEventListener('mouseup', stopDragBall)
}

// 拖动悬浮球
function dragBall(event) {
  if (!isDragging.value) return
  
  // 获取窗口尺寸和悬浮球尺寸
  const windowWidth = window.innerWidth
  const windowHeight = window.innerHeight
  const ballWidth = 60 // 悬浮球宽度，与CSS保持一致
  const ballHeight = 60 // 悬浮球高度，与CSS保持一致
  
  // 计算新位置
  let newX = event.clientX - dragOffset.value.x
  let newY = event.clientY - dragOffset.value.y
  
  // 边界检测
  // 左边界
  if (newX < 0) newX = 0
  // 右边界
  if (newX + ballWidth > windowWidth) newX = windowWidth - ballWidth
  // 上边界
  if (newY < 0) newY = 0
  // 下边界
  if (newY + ballHeight > windowHeight) newY = windowHeight - ballHeight
  
  // 应用新位置
  floatingBallPosition.value = {
    top: `${newY}px`,
    left: `${newX}px`
  }
  
  // 更新localStorage中的位置信息
  if (activeRoom.value) {
    activeRoom.value.position = floatingBallPosition.value
    localStorage.setItem('active_room', JSON.stringify(activeRoom.value))
  }
}

// 停止拖动悬浮球
function stopDragBall(event) {
  // 如果拖动距离很小，认为是点击
  const isClick = isDragging.value && 
                 Math.abs(event.clientX - (dragOffset.value.x + parseFloat(floatingBallPosition.value.left))) < 5 && 
                 Math.abs(event.clientY - (dragOffset.value.y + parseFloat(floatingBallPosition.value.top))) < 5;
  
  // 清理拖动状态和事件监听器
  isDragging.value = false;
  document.removeEventListener('mousemove', dragBall);
  document.removeEventListener('mouseup', stopDragBall);
  
  // 如果是点击行为，切换到迷你聊天
  if (isClick) {
    console.log('点击悬浮球，打开迷你聊天框');
    showFloatingBall.value = false;
    showMiniChat.value = true;
  }
}

// 返回房间
function returnToRoom() {
  console.log('准备返回房间，房间数据:', activeRoom.value);
  
  if (activeRoom.value && activeRoom.value.invite_code) {
    try {
      // 获取已缓存的消息历史
      const messages = activeRoom.value.messages || [];
      const secretMessages = activeRoom.value.secretMessages || [];
      
      // 暂存房间信息到tempRoomData中，确保RoomView能够获取到最新数据
      const roomInfo = {
        data: {
          invite_code: activeRoom.value.invite_code,
          room_data: {
            room_name: activeRoom.value.name,
            invite_code: activeRoom.value.invite_code,
            // 确保RoomView能知道这是从大厅返回的
            return_from_lobby: true,
            // 保存WebSocket连接状态
            connection_status: activeRoom.value.connection_status || 'disconnected',
            // 保存房主身份信息
            host_id: activeRoom.value.host_id
          }
        },
        success: true
      };
      
      // 不要在此处删除active_room数据，让RoomView去处理
      localStorage.setItem('tempRoomData', JSON.stringify(roomInfo));
      
      // 跳转前不要销毁悬浮球，以防路由跳转失败
      console.log('正在跳转到房间:', activeRoom.value.invite_code);
      router.push(`/room/${activeRoom.value.invite_code}`);
    } catch (error) {
      console.error('返回房间发生错误:', error);
      alert('返回房间失败，请刷新页面重试');
    }
  } else {
    console.error('找不到有效的房间信息');
    alert('房间信息丢失，请重新加入房间');
  }
}

function closeMiniChat() {
  showMiniChat.value = false;
  showFloatingBall.value = true;
}
</script>

<style scoped>
.lobby-container {
  min-height: 100vh;
  background-color: #f5f7fa;
  display: flex;
  flex-direction: column;
}

/* 顶部导航栏 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: white;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
  color: #3b71ca;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.create-room-btn, .join-room-btn {
  padding: 0.6rem 1rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border: none;
  border-radius: 4px;
  transition: all 0.2s;
}

.create-room-btn {
  background-color: #3b71ca;
  color: white;
}

.create-room-btn:hover {
  background-color: #2e5da3;
}

.join-room-btn {
  background-color: #28a745;
  color: white;
}

.join-room-btn:hover {
  background-color: #218838;
}

.icon {
  font-style: normal;
  font-weight: bold;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.username {
  font-weight: bold;
  color: #495057;
}

.avatar-container {
  position: relative;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #e9ecef;
}

.logout-btn {
  background-color: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.4rem 0.9rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background-color: #c82333;
}

/* 大厅内容区 */
.lobby-content {
  flex: 1;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  min-height: calc(100vh - 80px); /* 确保最小高度占满屏幕，减去顶部导航栏的高度 */
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.section-title {
  color: #495057;
  margin: 0;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #e9ecef;
  flex: 1;
}

.refresh-btn {
  background-color: #3b71ca;
  color: white;
  border: none;
  border-radius: 8px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  margin-left: 15px;
}

.refresh-btn:hover {
  background-color: #2c5697;
  transform: scale(1.05);
}

.refresh-btn:active {
  transform: scale(0.95);
}

.refresh-icon {
  font-size: 22px;
  font-weight: bold;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.refresh-btn.loading .refresh-icon {
  animation: spin 1s linear infinite;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8rem 1rem; /* 从5rem增加到8rem，增加垂直空间 */
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  min-height: 400px; /* 添加最小高度 */
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.empty-state h3 {
  font-size: 1.5rem;
  color: #495057;
  margin-bottom: 0.5rem;
}

.empty-state p {
  color: #6c757d;
}

/* 房间列表 */
.room-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  min-height: 500px; /* 添加最小高度，确保即使房间很少也有足够的空间 */
}

.room-card {
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  padding: 1.5rem;
  transition: transform 0.2s;
}

.room-card:hover {
  transform: translateY(-5px);
}

.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.room-name {
  font-size: 1.2rem;
  color: #495057;
  margin: 0;
}

.room-status {
  background-color: #28a745;
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  font-size: 0.8rem;
}

.room-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.join-room-card-btn {
  width: 100%;
  background-color: #3b71ca;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.6rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
}

.join-room-card-btn:hover {
  background-color: #2e5da3;
}

@media (max-width: 768px) {
  .header {
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
  }
  
  .logo {
    position: static;
    transform: none;
    order: -1;
  }
  
  .action-buttons {
    width: 100%;
  }
  
  .create-room-btn, .join-room-btn {
    flex: 1;
  }
  
  .user-info {
    width: 100%;
    justify-content: space-between;
  }
}

/* 创建房间弹窗样式 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.create-room-dialog {
  background-color: white;
  border-radius: 12px;
  width: 550px;
  max-width: 95%;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.dialog-header {
  padding: 18px 24px;
  background-color: #f8f9fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e9ecef;
}

.dialog-header h2 {
  margin: 0;
  font-size: 20px;
  color: #212529;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: #ff4d4f;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: transform 0.2s;
}

.close-btn:hover {
  transform: scale(1.2);
}

.dialog-body {
  padding: 24px;
  max-height: 65vh;
  overflow-y: auto;
}

.error-message {
  background-color: #ffebee;
  color: #d32f2f;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 20px;
  font-size: 14px;
  display: flex;
  align-items: center;
  border-left: 4px solid #f44336;
}

.form-group {
  margin-bottom: 18px;
}

.form-row {
  display: flex;
  gap: 16px;
  margin-bottom: 18px;
}

.form-row .form-group {
  flex: 1;
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #495057;
  font-size: 15px;
}

.help-text {
  font-size: 13px;
  color: #6c757d;
  font-weight: normal;
}

.input-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ced4da;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-control:focus {
  border-color: #4dabf7;
  box-shadow: 0 0 0 3px rgba(77, 171, 247, 0.2);
  outline: none;
}

.toggle-switch {
  display: flex;
  align-items: center;
}

/* 新样式开关 */
.switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 24px;
  margin-right: 12px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .4s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .4s;
}

input:checked + .slider {
  background-color: #3b71ca;
}

input:focus + .slider {
  box-shadow: 0 0 1px #3b71ca;
}

input:checked + .slider:before {
  transform: translateX(24px);
}

.slider.round {
  border-radius: 34px;
}

.slider.round:before {
  border-radius: 50%;
}

.toggle-label {
  font-size: 14px;
  color: #495057;
}

.dialog-footer {
  padding: 18px 24px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid #e9ecef;
}

.cancel-btn {
  padding: 10px 20px;
  background-color: #f8f9fa;
  color: #495057;
  border: 1px solid #ced4da;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s;
}

.cancel-btn:hover {
  background-color: #e9ecef;
}

.create-btn {
  padding: 10px 24px;
  background-color: #3b71ca;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s, transform 0.1s;
  box-shadow: 0 2px 5px rgba(59, 113, 202, 0.3);
}

.create-btn:hover {
  background-color: #2c5697;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(59, 113, 202, 0.4);
}

.create-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(59, 113, 202, 0.3);
}

/* 悬浮球样式 */
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
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.4);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(24, 144, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(24, 144, 255, 0);
  }
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
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  z-index: 1000;
  overflow: hidden;
}

.mini-chat-header {
  display: flex;
  align-items: center;
  padding: 12px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.mini-chat-header h3 {
  margin: 0;
  font-size: 16px;
  flex: 1;
  text-align: center;
  color: #333;
}

.back-button {
  display: flex;
  align-items: center;
  background: none;
  border: none;
  color: #1890ff;
  font-size: 14px;
  cursor: pointer;
  padding: 4px;
}

.back-button:hover {
  color: #40a9ff;
}

.mini-chat-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: #f9f9f9;
}

.mini-message {
  margin-bottom: 10px;
  text-align: center;
  max-width: 85%;
}

.system-message {
  color: #666;
  padding: 16px;
  font-size: 15px;
  background-color: #f0f0f0;
  border-radius: 8px;
}

.close-chat-button {
  background: none;
  border: none;
  color: #ff4d4f;
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.close-chat-button:hover {
  color: #ff7875;
}
</style>