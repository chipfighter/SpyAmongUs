<template>
  <div class="admin-page">
    <div class="admin-header">
      <h1 class="admin-title">管理员控制台</h1>
      <div class="admin-user-info">
        <img :src="userStore.userAvatar" alt="头像" class="admin-avatar" @error="onAvatarError">
        <div class="admin-username">{{ userStore.user?.username }}</div>
        <button @click="handleLogout" class="logout-btn" title="登出">
          退出
        </button>
      </div>
    </div>
    
    <!-- 悬浮球 - 用于快速返回房间 -->
    <FloatingBall 
      :show="showFloatingBall" 
      :room-name="activeRoom?.name || '房间'" 
      :position="{ top: '100px', left: '20px' }"
      @clicked="returnToRoom"
    />
    
    <div class="admin-content">
      <div class="admin-cards">
        <!-- 大厅按钮 -->
        <div class="admin-card" @click="navigateTo('lobby')">
          <div class="card-icon">🎮</div>
          <div class="card-title">游戏大厅</div>
          <div class="card-description">进入游戏大厅，与玩家一起体验游戏</div>
        </div>
        
        <!-- 玩家列表按钮 -->
        <div class="admin-card" @click="navigateTo('players')">
          <div class="card-icon">👥</div>
          <div class="card-title">玩家列表</div>
          <div class="card-description">查看在线玩家及其状态</div>
          <div class="card-badge" v-if="onlinePlayerCount > 0">{{ onlinePlayerCount }}</div>
        </div>
        
        <!-- 反馈信息按钮 -->
        <div class="admin-card" @click="navigateTo('feedback')">
          <div class="card-icon">📝</div>
          <div class="card-title">用户反馈</div>
          <div class="card-description">查看用户提交的反馈信息</div>
          <div class="card-badge" v-if="unreadFeedbackCount > 0">{{ unreadFeedbackCount }}</div>
        </div>
      </div>
      
      <!-- 面板内容区域 -->
      <div class="admin-panel" v-if="activePanel">
        <!-- 玩家列表面板 -->
        <div v-if="activePanel === 'players'" class="panel-content players-panel">
          <div class="panel-header">
            <h2 class="panel-title">用户列表</h2>
            <button class="refresh-button" @click="loadPlayers">刷新</button>
            <div class="filter-container">
              <select v-model="playerStatusFilter" class="filter-select">
                <option value="all">全部用户</option>
                <option value="online">在线用户</option>
                <option value="in_game">游戏中</option>
                <option value="offline">离线用户</option>
              </select>
            </div>
            <div class="search-container">
              <input type="text" v-model="playerSearchQuery" placeholder="搜索玩家..." class="search-input">
            </div>
          </div>
          
          <div class="panel-body">
            <div class="loading-spinner" v-if="loadingPlayers">加载中...</div>
            <div class="no-data-message" v-else-if="players.length === 0">当前没有任何用户</div>
            
            <div v-else class="players-stats">
              <div class="stat-item">
                <span class="stat-label">总用户数:</span>
                <span class="stat-value">{{ players.length }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">在线用户:</span>
                <span class="stat-value">{{ players.filter(p => p.status === 'online').length }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">游戏中用户:</span>
                <span class="stat-value">{{ players.filter(p => p.status === 'in_game').length }}</span>
              </div>
            </div>
            
            <table v-if="players.length > 0" class="data-table">
              <thead>
                <tr>
                  <th>用户名</th>
                  <th>状态</th>
                  <th>当前房间</th>
                  <th>登录时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="player in filteredPlayers" :key="player.id">
                  <td>
                    <div class="player-info">
                      <img :src="player.avatar_url || '/default_avatar.jpg'" class="player-avatar" @error="onAvatarError">
                      <span class="player-username" :class="{'is-admin': player.is_admin}">
                        {{ player.username }}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span class="status-badge" :class="player.status">
                      {{ getStatusText(player.status) }}
                    </span>
                  </td>
                  <td>
                    <span v-if="player.current_room">
                      {{ player.current_room }}
                      <button class="mini-button" @click="joinRoom(player.current_room)">加入</button>
                    </span>
                    <span v-else>-</span>
                  </td>
                  <td>{{ formatTime(player.last_login) }}</td>
                  <td>
                    <div class="action-buttons">
                      <button class="action-button" @click="mutePlayer(player)" :disabled="player.is_muted">禁言</button>
                      <button class="action-button danger" @click="banPlayer(player)" :disabled="player.is_banned">封禁</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        
        <!-- 反馈信息面板 -->
        <div v-if="activePanel === 'feedback'" class="panel-content feedback-panel">
          <div class="panel-header">
            <h2 class="panel-title">用户反馈</h2>
            <button class="refresh-button" @click="loadFeedback">刷新</button>
            <div class="filter-container">
              <select v-model="feedbackFilter" class="filter-select">
                <option value="all">全部</option>
                <option value="resolved">已解决</option>
                <option value="unresolved">未解决</option>
                <option value="game">游戏问题</option>
                <option value="feature">功能建议</option>
                <option value="performance">性能问题</option>
                <option value="ui">界面问题</option>
                <option value="other">其他</option>
              </select>
            </div>
          </div>
          
          <div class="panel-body">
            <div class="loading-spinner" v-if="loadingFeedback">加载中...</div>
            <div class="no-data-message" v-else-if="feedback.length === 0">没有符合条件的反馈信息</div>
            
            <div v-else class="feedback-container">
              <div class="feedback-list">
                <div 
                  v-for="item in filteredFeedback" 
                  :key="item.id"
                  class="feedback-item"
                  :class="{
                    'unread': !item.read, 
                    'active': selectedFeedback?.id === item.id,
                    'resolved': item.status === 'resolved',
                    'unresolved': item.status !== 'resolved'
                  }"
                  @click="selectFeedback(item)"
                >
                  <div class="feedback-item-header">
                    <span class="feedback-type-badge" :class="item.type">{{ getFeedbackTypeText(item.type) }}</span>
                    <span class="feedback-date">{{ formatDate(item.created_at) }}</span>
                  </div>
                  <div class="feedback-item-title">{{ item.title }}</div>
                  <div class="feedback-item-user">
                    <img :src="item.user_avatar || '/default_avatar.jpg'" class="feedback-user-avatar" @error="onAvatarError">
                    <span>{{ item.username }}</span>
                  </div>
                </div>
              </div>
              
              <div class="feedback-detail" v-if="selectedFeedback">
                <div class="feedback-detail-header">
                  <h3 class="feedback-detail-title">{{ selectedFeedback.title }}</h3>
                  <div class="feedback-detail-meta">
                    <span class="feedback-type-badge" :class="selectedFeedback.type">
                      {{ getFeedbackTypeText(selectedFeedback.type) }}
                    </span>
                    <span class="feedback-status-badge" :class="selectedFeedback.status === 'resolved' ? 'resolved' : 'unresolved'">
                      {{ selectedFeedback.status === 'resolved' ? '已解决' : '未解决' }}
                    </span>
                    <span class="feedback-date">提交于: {{ formatDate(selectedFeedback.created_at) }}</span>
                  </div>
                  <div class="feedback-detail-user">
                    <img :src="selectedFeedback.user_avatar || '/default_avatar.jpg'" class="feedback-user-avatar" @error="onAvatarError">
                    <span>{{ selectedFeedback.username }}</span>
                  </div>
                </div>
                
                <div class="feedback-detail-content">
                  {{ selectedFeedback.content }}
                </div>
                
                <div class="feedback-detail-actions">
                  <button 
                    class="action-button" 
                    @click="markAsResolved(selectedFeedback)"
                  >
                    {{ selectedFeedback.status === 'resolved' ? '标记为未解决' : '标记为已解决' }}
                  </button>
                  <button class="action-button" @click="respondToFeedback(selectedFeedback)">
                    回复
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/userStore'
import FloatingBall from '@/components/Room/FloatingBall.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 检查用户是否为管理员
onMounted(() => {
  if (!userStore.user?.is_admin) {
    router.push('/lobby')
  } else {
    // 获取初始数据
    loadPlayers()
    loadFeedback()
    
    // 检查是否从房间临时返回
    checkActiveRoom()
  }
})

// 检查是否有活动房间
const showFloatingBall = ref(false)
const activeRoom = ref(null)

const checkActiveRoom = () => {
  // 检查URL参数中是否有in_room=true
  const inRoom = route.query.in_room === 'true'
  
  // 从localStorage获取活动房间信息
  const roomData = localStorage.getItem('active_room')
  
  if (inRoom && roomData) {
    try {
      // 解析房间数据
      activeRoom.value = JSON.parse(roomData)
      showFloatingBall.value = true
    } catch (e) {
      console.error('解析房间数据失败:', e)
      localStorage.removeItem('active_room')
    }
  }
}

// 返回房间
const returnToRoom = () => {
  if (activeRoom.value?.roomId) {
    router.push(`/room/${activeRoom.value.roomId}`)
  }
}

// 面板控制
const activePanel = ref(null)
const navigateTo = (destination) => {
  if (destination === 'lobby') {
    router.push('/lobby')
  } else {
    activePanel.value = destination
    // 当切换到玩家列表面板时，刷新玩家数据
    if (destination === 'players') {
      loadPlayers()
    } else if (destination === 'feedback') {
      loadFeedback()
    }
  }
}

// 玩家列表相关
const players = ref([])
const loadingPlayers = ref(false)
const playerSearchQuery = ref('')
const onlinePlayerCount = ref(0)
const playerStatusFilter = ref('all')

const loadPlayers = async () => {
  loadingPlayers.value = true
  console.log('开始加载玩家列表...')
  
  try {
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/players`, {
      headers: {
        'Authorization': `Bearer ${userStore.accessToken}`
      }
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('获取到玩家列表数据:', result)
      if (result.success && result.data) {
        players.value = result.data
        onlinePlayerCount.value = players.value.filter(p => p.status === 'online').length
        console.log('在线玩家数量:', onlinePlayerCount.value)
        console.log('在线玩家:', players.value.filter(p => p.status === 'online'))
      }
    } else {
      console.error('获取玩家列表失败', await response.text())
    }
  } catch (error) {
    console.error('获取玩家列表错误:', error)
  } finally {
    loadingPlayers.value = false
  }
}

const filteredPlayers = computed(() => {
  // 先按状态过滤
  let filtered = players.value;
  if (playerStatusFilter.value !== 'all') {
    filtered = players.value.filter(player => player.status === playerStatusFilter.value);
  }
  
  // 再按搜索关键词过滤
  if (!playerSearchQuery.value) return filtered;
  
  const query = playerSearchQuery.value.toLowerCase();
  return filtered.filter(player => 
    player.username.toLowerCase().includes(query) || 
    (player.current_room && player.current_room.toLowerCase().includes(query))
  );
})

const getStatusText = (status) => {
  const statusMap = {
    'online': '在线',
    'in_game': '游戏中',
    'away': '离开',
    'offline': '离线'
  }
  return statusMap[status] || status
}

const formatTime = (timestamp) => {
  if (!timestamp) return '-'
  
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

const formatDate = (timestamp) => {
  if (!timestamp) return '-'
  
  // 确保时间戳是数字类型并且是毫秒级
  let ts = Number(timestamp)
  
  // 检查是否是秒级时间戳（长度为10左右），如果是则转换为毫秒级
  if (ts < 10000000000) {
    ts = ts * 1000
  }
  
  const date = new Date(ts)
  
  // 检查日期是否有效
  if (isNaN(date.getTime())) {
    return '无效日期'
  }
  
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const joinRoom = (roomId) => {
  router.push(`/room/${roomId}`)
}

const mutePlayer = async (player) => {
  if (confirm(`确定要禁言玩家 ${player.username}?`)) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/mute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userStore.accessToken}`
        },
        body: JSON.stringify({
          user_id: player.id,
          duration: 3600 // 禁言1小时
        })
      })
      
      if (response.ok) {
        alert(`已禁言玩家 ${player.username}`)
        loadPlayers() // 刷新列表
      } else {
        alert('禁言操作失败')
      }
    } catch (error) {
      console.error('禁言玩家错误:', error)
      alert('禁言操作失败')
    }
  }
}

const banPlayer = async (player) => {
  if (confirm(`确定要封禁玩家 ${player.username}?`)) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/ban`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userStore.accessToken}`
        },
        body: JSON.stringify({
          user_id: player.id,
          duration: 86400 // 封禁1天
        })
      })
      
      if (response.ok) {
        alert(`已封禁玩家 ${player.username}`)
        loadPlayers() // 刷新列表
      } else {
        alert('封禁操作失败')
      }
    } catch (error) {
      console.error('封禁玩家错误:', error)
      alert('封禁操作失败')
    }
  }
}

// 反馈信息相关
const feedback = ref([])
const loadingFeedback = ref(false)
const feedbackFilter = ref('all')
const selectedFeedback = ref(null)
const unreadFeedbackCount = ref(0)

const loadFeedback = async () => {
  loadingFeedback.value = true
  
  try {
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/feedbacks`, {
      headers: {
        'Authorization': `Bearer ${userStore.accessToken}`
      }
    })
    
    if (response.ok) {
      const result = await response.json()
      if (result.success && result.data) {
        feedback.value = result.data
        unreadFeedbackCount.value = feedback.value.filter(f => !f.read).length
      }
    } else {
      console.error('获取反馈信息失败')
    }
  } catch (error) {
    console.error('获取反馈信息错误:', error)
  } finally {
    loadingFeedback.value = false
  }
}

const filteredFeedback = computed(() => {
  if (feedbackFilter.value === 'all') return feedback.value
  if (feedbackFilter.value === 'resolved') return feedback.value.filter(f => f.status === 'resolved')
  if (feedbackFilter.value === 'unresolved') return feedback.value.filter(f => f.status !== 'resolved')
  return feedback.value.filter(f => f.type === feedbackFilter.value)
})

const getFeedbackTypeText = (type) => {
  const typeMap = {
    'game': '游戏问题',
    'feature': '功能建议',
    'performance': '性能问题',
    'ui': '界面问题',
    'other': '其他'
  }
  return typeMap[type] || type
}

const selectFeedback = (item) => {
  selectedFeedback.value = item
}

const markAsResolved = async (item) => {
  try {
    // 根据当前状态决定新的状态值
    const newStatus = item.status === 'resolved' ? 'pending' : 'resolved'
    
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/feedback/${item.id}/update-status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userStore.accessToken}`
      },
      body: JSON.stringify({ status: newStatus })
    })
    
    if (response.ok) {
      // 更新本地状态
      item.read = true
      item.status = newStatus
      unreadFeedbackCount.value = feedback.value.filter(f => !f.read).length
      // 刷新反馈列表
      loadFeedback()
    }
  } catch (error) {
    console.error('更新反馈状态错误:', error)
  }
}

const respondToFeedback = async (item) => {
  const message = prompt('请输入回复内容:')
  if (!message) return
  
  try {
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/feedback/${item.id}/respond`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userStore.accessToken}`
      },
      body: JSON.stringify({ message })
    })
    
    if (response.ok) {
      alert('回复已发送')
      // 标记为已读
      item.read = true
      unreadFeedbackCount.value = feedback.value.filter(f => !f.read).length
    } else {
      alert('回复发送失败')
    }
  } catch (error) {
    console.error('回复反馈错误:', error)
    alert('回复发送失败')
  }
}

// 通用方法
const onAvatarError = (e) => {
  e.target.src = '/default_avatar.jpg'
}

const handleLogout = async () => {
  await userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-page {
  min-height: 100vh;
  background-color: #f3f4f6;
  color: #333;
}

.admin-header {
  background-color: #fff;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.admin-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.admin-user-info {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.admin-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #4a6cf7;
}

.admin-username {
  font-weight: 500;
}

/* 退出按钮样式，与大厅样式一致 */
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

.admin-content {
  display: flex;
  flex-direction: column;
  max-width: 1400px;
  margin: 0 auto;
  padding: 2rem;
  gap: 2rem;
}

.admin-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2rem;
}

.admin-card {
  background-color: #fff;
  border-radius: 12px;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  position: relative;
  height: 250px;
}

.admin-card:hover {
  transform: translateY(-10px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}

.card-icon {
  font-size: 3rem;
  margin-bottom: 1.5rem;
}

.card-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: #333;
}

.card-description {
  color: #666;
  line-height: 1.5;
}

.card-badge {
  position: absolute;
  top: -10px;
  right: -10px;
  background-color: #ff4757;
  color: white;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

/* 面板样式 */
.admin-panel {
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.panel-header {
  padding: 1.2rem 1.5rem;
  background-color: #f8f9fa;
  border-bottom: 1px solid #eaeaea;
  display: flex;
  align-items: center;
}

.panel-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  flex: 1;
}

.refresh-button {
  background-color: #4a6cf7;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.refresh-button:hover {
  background-color: #3a5ce5;
}

.search-container, .filter-container {
  margin-left: 1rem;
  width: 250px;
}

.search-input, .filter-select {
  width: 100%;
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.9rem;
}

.panel-body {
  padding: 1.5rem;
  max-height: 600px;
  overflow-y: auto;
}

/* 表格样式 */
.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  background-color: #f8f9fa;
  padding: 0.8rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #555;
  border-bottom: 2px solid #eaeaea;
}

.data-table td {
  padding: 0.8rem 1rem;
  border-bottom: 1px solid #eaeaea;
}

.player-info {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.player-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}

.player-username {
  font-weight: 500;
}

.player-username.is-admin {
  color: #4a6cf7;
  position: relative;
}

.player-username.is-admin::after {
  content: "管理员";
  position: absolute;
  top: -8px;
  right: -60px;
  font-size: 0.7rem;
  background-color: #4a6cf7;
  color: white;
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: normal;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 500;
}

.status-badge.online {
  background-color: #e7f8e8;
  color: #28c76f;
}

.status-badge.in_game {
  background-color: #e9ecff;
  color: #4a6cf7;
}

.status-badge.away {
  background-color: #fff8e6;
  color: #ffc107;
}

.status-badge.offline {
  background-color: #f8f9fa;
  color: #6c757d;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.action-button {
  padding: 0.35rem 0.7rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  background-color: #4a6cf7;
  color: white;
  transition: all 0.2s;
}

.action-button:hover {
  opacity: 0.9;
}

.action-button.danger {
  background-color: #ff4757;
}

.action-button:disabled {
  background-color: #e1e1e1;
  color: #999;
  cursor: not-allowed;
}

.mini-button {
  padding: 0.2rem 0.4rem;
  font-size: 0.75rem;
  background-color: #f1f3f9;
  color: #4a6cf7;
  border: 1px solid #e3e8f7;
  border-radius: 3px;
  cursor: pointer;
  margin-left: 0.5rem;
}

.mini-button:hover {
  background-color: #e3e8f7;
}

/* 反馈面板样式 */
.feedback-container {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 1.5rem;
}

.feedback-list {
  border-right: 1px solid #eaeaea;
  overflow-y: auto;
  max-height: 550px;
}

.feedback-item {
  padding: 1rem;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: all 0.2s;
}

.feedback-item:hover {
  background-color: #f9f9f9;
}

.feedback-item.unread {
  background-color: #f0f7ff;
}

.feedback-item.active {
  background-color: #e3f2fd;
  border-left: 3px solid #4a6cf7;
}

.feedback-item.resolved {
  background-color: #e7f8e8;
  border-left: 3px solid #28c76f;
}

.feedback-item.unresolved {
  background-color: #fff8e6;
  border-left: 3px solid #ff9500;
}

.feedback-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.feedback-type-badge {
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
}

.feedback-type-badge.game {
  background-color: #ffe7e7;
  color: #ff4757;
}

.feedback-type-badge.feature {
  background-color: #e7f8e8;
  color: #28c76f;
}

.feedback-type-badge.performance {
  background-color: #fff8e6;
  color: #ff9500;
}

.feedback-type-badge.ui {
  background-color: #e7f0fb;
  color: #4a6cf7;
}

.feedback-type-badge.other {
  background-color: #f8f9fa;
  color: #6c757d;
}

.feedback-date {
  font-size: 0.8rem;
  color: #888;
}

.feedback-item-title {
  font-weight: 500;
  margin-bottom: 0.5rem;
  color: #333;
}

.feedback-item-user {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #666;
}

.feedback-user-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  object-fit: cover;
}

.feedback-detail {
  padding: 1rem;
}

.feedback-detail-header {
  margin-bottom: 1.5rem;
}

.feedback-detail-title {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
  color: #333;
}

.feedback-detail-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.8rem;
}

.feedback-detail-user {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-top: 1rem;
}

.feedback-detail-user img {
  width: 32px;
  height: 32px;
}

.feedback-detail-content {
  padding: 1.5rem;
  background-color: #f9f9f9;
  border-radius: 8px;
  line-height: 1.6;
  min-height: 300px;
  margin-bottom: 1.5rem;
  white-space: pre-line;
}

.feedback-detail-actions {
  display: flex;
  gap: 1rem;
}

/* 加载和空数据状态 */
.loading-spinner {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.no-data-message {
  text-align: center;
  padding: 2rem;
  color: #888;
  font-style: italic;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .admin-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .admin-cards {
    grid-template-columns: 1fr;
  }
  
  .feedback-container {
    grid-template-columns: 1fr;
  }
  
  .panel-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.8rem;
  }
  
  .search-container, .filter-container {
    width: 100%;
    margin-left: 0;
  }
}

.feedback-status-badge {
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
}

.feedback-status-badge.resolved {
  background-color: #e7f8e8;
  color: #28c76f;
}

.feedback-status-badge.unresolved {
  background-color: #fff8e6;
  color: #ff9500;
}

.players-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  background-color: white;
  padding: 10px 20px;
  border-radius: 6px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
}

.stat-label {
  font-size: 0.85rem;
  color: #666;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 1.2rem;
  font-weight: bold;
  color: #333;
}
</style> 