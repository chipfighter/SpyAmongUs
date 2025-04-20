<template>
  <div class="lobby-container" @click.self="closeContextMenuAndDialogs">
    <!-- WebSocket 连接加载指示器 -->
    <div v-if="isConnectingWebSocket" class="websocket-loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">正在连接房间...</div>
    </div>
    <!-- 结束加载指示器 -->

    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="action-buttons">
        <button class="create-room-btn" @click="openCreateRoomDialog">
          <i class="icon">+</i> 创建房间
        </button>
        <button class="join-room-btn" @click="openJoinRoomDialog">
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
        <button class="refresh-btn" :class="{ 'refreshing': isRefreshing }" title="刷新房间列表" @click="refreshRooms">
          <span class="refresh-icon">↻</span>
        </button>
      </div>
      
      <!-- 加载状态 -->
      <div v-if="isLoading" class="loading-state">正在加载房间...</div>

      <!-- 空状态 -->
      <div class="empty-state" v-if="!isLoading && publicRooms.length === 0">
        <div class="empty-icon">🏠</div>
        <h3>暂无公开房间</h3>
        <p>点击顶部按钮创建或加入房间</p>
      </div>
      
      <!-- 房间列表 - 更新结构和样式 -->
      <div class="room-list" v-if="!isLoading && publicRooms.length > 0">
        <div 
          class="room-card" 
          v-for="room in publicRooms" 
          :key="room.invite_code"
          @click.stop="showContextMenu($event, room)" 
          @contextmenu.prevent="showContextMenu($event, room)"
        >
          <img 
            :src="room.host_avatar_url || '/default_avatar.jpg'" 
            alt="房主头像" 
            class="host-avatar"
            @error="onAvatarError"
          />
          
          <div class="room-card-content">
            <h3 class="room-name">{{ room.room_name }}</h3>
            <div class="room-details">
              <span class="room-players">
                <i class="fas fa-users"></i> {{ room.current_players }}/{{ room.total_players }}
              </span>
              <span class="room-status" :class="room.status">
                {{ room.status === 'waiting' ? '等待中' : '游戏中' }}
              </span>
            </div>
          </div>
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

    <!-- 新增：加入房间弹窗 -->
    <div class="dialog-overlay" v-if="showJoinRoomDialog" @click.self="showJoinRoomDialog = false">
      <div class="join-room-dialog">
        <div class="dialog-header">
          <h2>加入房间</h2>
          <button class="close-btn" @click="showJoinRoomDialog = false">×</button>
        </div>
        <div class="dialog-body">
          <div class="error-message" v-if="joinFormError">
            {{ joinFormError }}
          </div>
          <div class="form-group">
            <label for="invite-code-input">房间邀请码</label>
            <input 
              id="invite-code-input"
              v-model="inviteCodeInput" 
              type="text" 
              placeholder="输入房间的邀请码"
              class="input-control"
              @keyup.enter="handleJoinFromDialog"
            >
          </div>
        </div>
        <div class="dialog-footer">
          <button class="cancel-btn" @click="showJoinRoomDialog = false">取消</button>
          <button class="create-btn" @click="handleJoinFromDialog">
            <i class="icon">→</i> 确认加入
          </button>
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

    <!-- 新增：上下文菜单 -->
    <div 
      v-if="contextMenuVisible" 
      class="context-menu" 
      :style="{ top: contextMenuPosition.top + 'px', left: contextMenuPosition.left + 'px' }"
      @click.stop
    >
      <div class="context-menu-item" @click="handleJoinFromMenu">
        <i class="fas fa-sign-in-alt"></i> 加入房间
      </div>
      <div class="context-menu-item disabled">
        <i class="fas fa-info-circle"></i> 房间详情 (暂不可用)
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/userStore'
import { useWebsocketStore } from '../stores/websocket'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const websocketStore = useWebsocketStore()

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

// 新增：加入房间弹窗相关
const showJoinRoomDialog = ref(false)
const inviteCodeInput = ref('')
const joinFormError = ref('')

// 房间列表相关
const publicRooms = ref([])
const isLoading = ref(true)
const isRefreshing = ref(false)

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

// 上下文菜单状态
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ top: 0, left: 0 })
const contextMenuRoom = ref(null)

const isConnectingWebSocket = ref(false)
const webSocketConnectionError = ref(null)

// 在顶部变量声明部分添加
const autoRefreshInterval = ref(null);

// 添加一个防重复刷新的标志
const isRefreshingInProgress = ref(false);

// 避免短时间内多次刷新
const lastRefreshTime = ref(0);

onMounted(async () => {
  // 初始用户数据
  userStore.initStore()
  
  // 如果没有登录则跳转到登录页并提前返回
  if (!userStore.isAuthenticated) {
    console.log('[LobbyView] 用户未登录，跳转到登录页');
    router.push('/login');
    return; // 提前返回，避免执行后续需要认证的API请求
  }

  // 以下代码只在已登录状态下执行
  console.log('[LobbyView] 用户已登录，初始化大厅');
  
  // 检查路由参数，确定是否是从房间回来的
  const fromRoom = route.query.from_room === 'true';
  const initialLoad = ref(true);
  
  // 初始加载时刷新一次（场景1）
  console.log('[LobbyView] 初始加载刷新（场景1）');
  await refreshRooms();
  
  // 检查是否有活动房间并显示悬浮球
  checkActiveRoom();
  
  // 添加全局点击监听器
  document.addEventListener('click', handleClickOutsideMenu);
  
  // 启动自动刷新计时器（场景4）
  startAutoRefresh();
  
  // 添加页面可见性变化监听
  document.addEventListener('visibilitychange', handleVisibilityChange);
  
  // 移除先前的afterEach监听器（如果有）
  if (window._lobbyRouteGuard) {
    if (router.afterEach.indexOf && router.afterEach.indexOf(window._lobbyRouteGuard) > -1) {
      router.afterEach.splice(router.afterEach.indexOf(window._lobbyRouteGuard), 1);
    }
  }
  
  // 延迟设置路由钩子，避免与初始加载冲突
  setTimeout(() => {
    initialLoad.value = false;
    
    // 添加路由变化监听，用于检测用户从房间返回大厅
    window._lobbyRouteGuard = (to, from) => {
      // 仅当从房间页面导航到大厅页面，且不是初始加载时触发刷新
      if (!initialLoad.value && (to.name === 'lobby' || to.path === '/') && from.path.includes('/room/')) {
        console.log('[LobbyView] 检测到从房间返回大厅，准备刷新');
        
        // 避免重复刷新，一定时间内只刷新一次
        const now = Date.now();
        if (!lastRefreshTime.value || (now - lastRefreshTime.value > 3000)) {
          lastRefreshTime.value = now;
          
          // 确保不会与初始加载冲突
          if (!isRefreshingInProgress.value) {
            refreshRooms();
            // 重启自动刷新计时器
            startAutoRefresh();
          }
        } else {
          console.log('[LobbyView] 跳过刷新，因为距离上次刷新时间太短');
        }
      }
    };
    
    router.afterEach(window._lobbyRouteGuard);
  }, 300); // 减少等待时间，提高响应速度
})

onBeforeUnmount(() => {
  // 移除可能添加的事件监听器
  document.removeEventListener('mousemove', dragBall)
  document.removeEventListener('mouseup', stopDragBall)
  // 移除全局点击监听器
  document.removeEventListener('click', handleClickOutsideMenu)
  
  // 停止自动刷新并移除页面可见性监听
  stopAutoRefresh()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

// 修改refreshRooms函数，保证所有场景下刷新动画一致
async function refreshRooms() {
  // 避免并发刷新请求
  if (isRefreshingInProgress.value) {
    console.log('[LobbyView] 刷新操作正在进行中，跳过重复刷新');
    return;
  }
  
  isRefreshingInProgress.value = true;
  isLoading.value = true;
  isRefreshing.value = true; // 确保按钮动画显示
  
  console.log('[LobbyView] 开始刷新房间列表', new Date().toLocaleTimeString());
  
  try {
    // 检查登录状态，确保有token再发请求
    if (!userStore.accessToken) {
      console.error('[LobbyView] 刷新失败：用户未登录或token无效');
      throw new Error('用户未登录或token无效');
    }
    
    // 调用API获取公开房间列表
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/rooms/refresh_public_room`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${userStore.accessToken}`
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
      console.error('[LobbyView] 刷新房间列表失败:', response.status);
      publicRooms.value = [];
    }
  } catch (error) {
    console.error('[LobbyView] 获取房间列表失败:', error);
    publicRooms.value = [];
  } finally {
    isLoading.value = false;
    
    // 保证动画至少显示1秒 - 统一所有场景的刷新体验
    setTimeout(() => {
      isRefreshing.value = false;
      isRefreshingInProgress.value = false;
      console.log('[LobbyView] 刷新动画结束，解除锁定');
    }, 1000);
  }
}

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}

// 新增：打开创建房间对话框前的检查
const openCreateRoomDialog = () => {
  if (userStore.user?.current_room) {
    alert('您已在一个房间中，请先退出或返回房间后再创建。');
  } else {
    showCreateRoomDialog.value = true;
    formError.value = ''; // 清空之前的错误
  }
};

// 新增：打开加入房间对话框前的检查
const openJoinRoomDialog = () => {
  if (userStore.user?.current_room) {
    alert('您已在一个房间中，请先退出或返回房间后再加入。');
  } else {
    showJoinRoomDialog.value = true;
    joinFormError.value = ''; // 清空之前的错误
    inviteCodeInput.value = ''; // 清空输入框
  }
};

// 创建房间方法
const validateAndCreateRoom = async () => {
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
  formError.value = ''
  // --- Show initial loading for API call (optional, could be part of WebSocket loading) ---
  // isLoading.value = true; 
  
  try {
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/create_room`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userStore.accessToken}`
      },
      body: JSON.stringify(roomData.value)
    })
    const result = await response.json()
    
    // isLoading.value = false; // Hide initial loading
    
    if (result.success && result.data?.invite_code) {
      showCreateRoomDialog.value = false
      const roomId = result.data.invite_code;
      console.log(`Room created successfully with ID: ${roomId}. Connecting WebSocket...`);
      // --- Call the helper function --- 
      await connectAndNavigate(roomId);
      // --- Remove direct navigation --- 
      // router.push(`/room/${roomId}`)
    } else {
      formError.value = result.message || '创建房间失败'
      console.error('创建房间失败:', result)
    }
  } catch (error) {
    // isLoading.value = false; // Hide initial loading on error
    formError.value = '创建房间时发生错误，请重试'
    console.error('创建房间错误:', error)
  }
}

// 处理弹窗加入
const handleJoinFromDialog = async () => {
  if (!inviteCodeInput.value.trim()) {
    joinFormError.value = '请输入邀请码'
    return
  }
  await joinRoom(inviteCodeInput.value.trim())
}

// 加入房间核心逻辑
const joinRoom = async (roomId) => {
  joinFormError.value = ''
  // --- Show initial loading for API call (optional) ---
  // isLoading.value = true; 

  try {
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/room/${roomId}/join_room`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userStore.accessToken}`
      }
    })
    const result = await response.json()
    
    // isLoading.value = false; // Hide initial loading
    
    if (result.success) {
      showJoinRoomDialog.value = false
      inviteCodeInput.value = ''
      console.log(`Joined room successfully: ${roomId}. Connecting WebSocket...`);
      // --- Call the helper function --- 
      await connectAndNavigate(roomId);
      // --- Remove direct navigation --- 
      // router.push(`/room/${roomId}`)
    } else {
      if (showJoinRoomDialog.value) {
         joinFormError.value = result.message || '加入房间失败'
      } else {
         // Handle error if join initiated from context menu (e.g., global notification)
         alert(`加入房间失败: ${result.message || '请重试'}`);
      }
      console.error('加入房间失败:', result)
    }
  } catch (error) {
    // isLoading.value = false; // Hide initial loading on error
    if (showJoinRoomDialog.value) {
       joinFormError.value = '加入房间时发生错误，请重试'
    } else {
       alert('加入房间时发生错误，请重试');
    }
    console.error('加入房间错误:', error)
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

// --- 新增：上下文菜单逻辑 ---
function showContextMenu(event, room) {
  event.preventDefault(); // 阻止默认右键菜单
  contextMenuRoom.value = room; // 保存被点击的房间信息

  // 确保菜单先隐藏再计算位置，避免旧尺寸影响
  contextMenuVisible.value = false; 
  
  nextTick(() => { // 在DOM更新后计算位置
      const menuWidth = 150; // 菜单大致宽度
      const menuHeight = 80; // 菜单大致高度
      const clickX = event.clientX;
      const clickY = event.clientY;
      const screenWidth = window.innerWidth;
      const screenHeight = window.innerHeight;

      let left = clickX;
      let top = clickY;

      // 防止菜单超出屏幕右侧
      if (clickX + menuWidth > screenWidth) {
          left = screenWidth - menuWidth - 5; // 留一点边距
      }
      // 防止菜单超出屏幕底部
      if (clickY + menuHeight > screenHeight) {
          top = screenHeight - menuHeight - 5; // 留一点边距
      }
       // 防止菜单超出屏幕左侧 (虽然一般不会)
      if (left < 0) left = 5;
      // 防止菜单超出屏幕顶部 (虽然一般不会)
      if (top < 0) top = 5;


      contextMenuPosition.value = { top, left };
      contextMenuVisible.value = true;
  });
}

function closeContextMenu() {
  contextMenuVisible.value = false;
  contextMenuRoom.value = null;
}

function handleClickOutsideMenu(event) {
  // 简单的判断逻辑，如果点击事件的目标不是菜单本身或其子元素，则关闭
  // 注意：这种方式可能不够完美，更健壮的方式是检查 event.target 是否在 context-menu 元素内部
  if (contextMenuVisible.value) {
      // 查找 .context-menu 元素
      const menuElement = document.querySelector('.context-menu');
      const joinDialogElement = document.querySelector('.join-room-dialog'); // 检查是否点击了加入房间弹窗内部
      const createDialogElement = document.querySelector('.create-room-dialog'); // 检查是否点击了创建房间弹窗内部

      // 如果点击事件的目标不在菜单内，也不在任何打开的弹窗内，则关闭菜单
      if (menuElement && !menuElement.contains(event.target) && 
          (!joinDialogElement || !joinDialogElement.contains(event.target)) &&
          (!createDialogElement || !createDialogElement.contains(event.target)) ) {
           closeContextMenu();
      }
  }
}

// 处理右键菜单加入
const handleJoinFromMenu = async () => {
  if (contextMenuRoom.value?.invite_code) {
    contextMenuVisible.value = false
    await joinRoom(contextMenuRoom.value.invite_code)
  }
}

// 新增：处理头像加载失败
function onAvatarError(event) {
  event.target.src = '/default_avatar.jpg'; // 设置为默认头像
}

// --- 新增：统一关闭所有弹窗和菜单 ---
function closeContextMenuAndDialogs() {
  closeContextMenu()
  // 如果有其他弹窗，也在这里关闭
  // showCreateRoomDialog.value = false;
  // showJoinRoomDialog.value = false;
}

// --- 结束：上下文菜单逻辑 ---

// --- Helper function to handle WebSocket connection and navigation --- 
const connectAndNavigate = async (roomId) => {
  if (!roomId) {
    console.error('connectAndNavigate failed: roomId is missing');
    return; 
  }
  
  isConnectingWebSocket.value = true;
  webSocketConnectionError.value = null; // Reset previous error
  
  const token = userStore.accessToken; // Get current token
  if (!token) {
     console.error('WebSocket connection failed: Missing token');
     webSocketConnectionError.value = '登录信息丢失，无法连接房间';
     isConnectingWebSocket.value = false;
     return;
  }
  
  // Start connection
  websocketStore.connect(roomId, token);
  
  // Watch for connection status changes
  const stopWatch = watch(() => websocketStore.connectionStatus, (newStatus, oldStatus) => {
    console.log(`[LobbyView Watcher] WebSocket status changed: ${oldStatus} -> ${newStatus}`);
    if (newStatus === 'connected') {
      console.log('[LobbyView Watcher] WebSocket connected! Navigating...');
      isConnectingWebSocket.value = false;
      stopWatch(); // Stop watching once connected
      router.push(`/room/${roomId}`);
    } else if (newStatus === 'disconnected' && oldStatus === 'connecting') {
      // Connection failed during the attempt
      console.error('[LobbyView Watcher] WebSocket connection failed during attempt.');
      isConnectingWebSocket.value = false;
      webSocketConnectionError.value = '无法连接到房间服务器，请稍后重试或检查网络。'; 
      stopWatch(); // Stop watching on failure
      // Optionally disconnect if needed, though handleClose should manage state
      // websocketStore.disconnect(); 
    }
    // We might need to handle cases where it disconnects *after* being connected briefly
    // but that might be better handled globally or in RoomView.
  }, { immediate: false }); // Don't run immediately

  // Timeout for the watcher itself, in case connection hangs indefinitely
  setTimeout(() => {
      if (isConnectingWebSocket.value) { // Still waiting?
          console.error('[LobbyView Watcher] Timeout waiting for WebSocket connection.');
          stopWatch();
          isConnectingWebSocket.value = false;
          webSocketConnectionError.value = '连接房间超时，请重试。';
          websocketStore.disconnect(true); // Force disconnect state
      }
  }, 15000); // 15 second timeout for connection attempt
};
// --------------------------------------------------------------------

// --- Add watcher for WebSocket errors to potentially show in Lobby --- 
watch(webSocketConnectionError, (newError) => {
  if (newError) {
      // Show error to the user (e.g., using a toast notification or a dedicated error area)
      // For now, just use alert
      alert(`连接错误: ${newError}`); 
      // Optionally clear the error after showing it
      // setTimeout(() => { webSocketConnectionError.value = null; }, 5000);
  }
});

// 修改startAutoRefresh函数，确保先停止旧计时器，并增加日志
function startAutoRefresh() {
  // 确保先停止旧计时器
  stopAutoRefresh();
  
  // 只有在页面可见时才启动自动刷新
  if (document.visibilityState === 'visible') {
    console.log('[LobbyView] 启动自动刷新计时器，间隔15秒');
    autoRefreshInterval.value = setInterval(() => {
      // 只在页面可见且没有正在进行刷新时才刷新
      if (document.visibilityState === 'visible' && !isRefreshingInProgress.value) {
        console.log('[LobbyView] 自动刷新计时器触发', new Date().toLocaleTimeString());
        refreshRooms();
      } else {
        console.log('[LobbyView] 跳过自动刷新，因为页面不可见或上一次刷新尚未完成');
      }
    }, 15000); // 15秒
    
    console.log('[LobbyView] 设置了新的自动刷新计时器ID:', autoRefreshInterval.value);
  } else {
    console.log('[LobbyView] 页面不可见，不启动自动刷新计时器');
  }
}

function stopAutoRefresh() {
  if (autoRefreshInterval.value) {
    console.log('[LobbyView] 停止自动刷新计时器ID:', autoRefreshInterval.value);
    clearInterval(autoRefreshInterval.value);
    autoRefreshInterval.value = null;
  } else {
    console.log('[LobbyView] 没有找到活动的自动刷新计时器');
  }
}

// 处理页面可见性变化
function handleVisibilityChange() {
  const isVisible = document.visibilityState === 'visible';
  console.log('[LobbyView] 页面可见性变化:', isVisible ? '可见' : '不可见', new Date().toLocaleTimeString());
  
  if (isVisible) {
    // 页面变为可见时，立即刷新一次
    if (!isRefreshingInProgress.value) {
      console.log('[LobbyView] 页面变为可见，立即刷新一次');
      refreshRooms();
    }
    
    // 启动自动刷新
    console.log('[LobbyView] 页面变为可见，启动自动刷新');
    startAutoRefresh();
  } else {
    // 页面不可见时停止自动刷新
    console.log('[LobbyView] 页面变为不可见，停止自动刷新');
    stopAutoRefresh();
  }
}
</script>

<style scoped>
/* --- Add styles for WebSocket loading overlay --- */
.websocket-loading-overlay {
  position: fixed; /* Or absolute if lobby-container is relative */
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(255, 255, 255, 0.7); /* Semi-transparent white */
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 2000; /* Ensure it's above other elements */
}

/* Reuse existing spinner styles if available, or define new ones */
.loading-spinner { 
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: 5px solid #f3f3f3;
  border-top: 5px solid #1890ff; /* Adjust color if needed */
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
/* --- End WebSocket loading styles --- */

.lobby-container {
  min-height: 100vh;
  background-color: #f5f7fa;
  display: flex;
  flex-direction: column;
  position: relative; /* 确保弹窗定位正确 */
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
  position: relative; /* 确保上下文菜单定位正确 */
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

.refresh-btn.refreshing .refresh-icon {
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
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  padding-bottom: 2rem;
}

.room-card {
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.07);
  padding: 1rem 1.2rem;
  transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
  position: relative;
  overflow: hidden;
  cursor: pointer;
  min-height: 100px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.room-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
}

.host-avatar {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  background-color: #eee;
}

.room-card-content {
  padding-right: 45px;
}

.room-name {
  font-size: 1.15rem;
  color: #333;
  margin: 0 0 0.6rem 0;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: #666;
}

.room-players {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.room-players i {
  color: #888;
}

.room-status {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 500;
  font-size: 0.75rem;
}

.room-status.waiting {
  background-color: #e6f7ff;
  color: #1890ff;
  border: 1px solid #91d5ff;
}

.room-status.playing {
  background-color: #fffbe6;
  color: #faad14;
  border: 1px solid #ffe58f;
}

/* 移除旧的按钮和信息 */
.room-header, .room-info, .join-room-card-btn, .room-host {
  display: none !important;
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

/* 上下文菜单样式 */
.context-menu {
  position: fixed;
  z-index: 1010;
  background-color: white;
  border-radius: 6px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.15);
  padding: 6px 0;
  min-width: 160px;
  border: 1px solid #eee;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 9px 16px;
  font-size: 0.9rem;
  color: #333;
  cursor: pointer;
  transition: background-color 0.15s ease-in-out;
  white-space: nowrap;
}
.context-menu-item i {
  color: #666;
  width: 16px;
  text-align: center;
}

.context-menu-item:hover {
  background-color: #f5f5f5;
}

.context-menu-item.disabled {
  color: #aaa;
  cursor: not-allowed;
  background-color: transparent;
}
.context-menu-item.disabled:hover {
   background-color: transparent;
}
.context-menu-item.disabled i {
   color: #ccc;
}

/* 响应式调整：在中等屏幕下每行显示2个 */
@media (max-width: 992px) {
  .room-list {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 响应式调整：在小屏幕下每行显示1个 */
@media (max-width: 600px) {
  .room-list {
    grid-template-columns: 1fr;
  }
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
    order: 1;
  }
  .create-room-btn, .join-room-btn {
    flex: 1;
  }
  .user-info {
    width: 100%;
    justify-content: space-between;
  }
}

/* 加入房间弹窗特定样式 (复用大部分创建房间弹窗样式) */
.join-room-dialog {
  background-color: white;
  border-radius: 12px;
  width: 400px; /* 比创建房间小一点 */
  max-width: 90%;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

/* 加入房间弹窗的按钮图标 */
.join-room-dialog .create-btn .icon {
  font-style: normal;
  font-weight: bold;
  margin-right: 0.3rem; /* 图标和文字间距 */
}
</style>