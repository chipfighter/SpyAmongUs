<template>
  <div class="users-container" :class="{ 'collapsed': isCollapsed, 'transitioning': isTransitioning }">
    <div class="resize-handle" @mousedown="emit('start-resize', $event)"></div>
    <div class="users-header">
      <button class="collapse-btn" @click="handleToggleCollapse">
        {{ isCollapsed ? '◀' : '▶' }}
      </button>
      <h3>玩家列表 ({{ users.length }}/{{ totalPlayers || 8 }})</h3>
    </div>
    
    <div class="users-list">
      <!-- 真实用户 -->
      <div v-for="user in users" :key="user.id" class="user-item" @click="user.id !== currentUserId && toggleActionButtons(user.id)">
        <div class="user-avatar">
          <img :src="user.avatar_url || '/default_avatar.jpg'" alt="用户头像" @error="onAvatarError">
          <span v-if="user.id === hostId" class="host-badge">房主</span>
        </div>
        <div class="user-name">
          {{ user.username || user.username }}
          <!-- 仅在游戏未开始且正在轮询上帝之前显示准备状态 -->
          <span v-if="readyUsers.includes(user.id) && !gameStarted && !isGodPolling" class="ready-badge">准备</span>
          
          <!-- 添加身份显示，仅在游戏已开始且分配了角色后显示 -->
          <span v-if="gameStarted && roles && shouldShowRole(user.id)" class="role-badge" :class="getRoleClass(user.id)">
            {{ getRoleName(user.id) }}
          </span>
        </div>
        
        <!-- 用户操作按钮组 - 只对非当前用户显示 -->
        <div v-if="selectedUserId === user.id && user.id !== currentUserId && !gameStarted" class="user-actions">
          <button class="action-btn" title="添加好友" @click.stop="emit('add-friend', user.id)">
            <i class="action-icon">👥</i>
            <span class="action-text">添加好友</span>
          </button>
          <button class="action-btn" title="用户详情" @click.stop="emit('view-user-details', user.id)">
            <i class="action-icon">ℹ️</i>
            <span class="action-text">用户详情</span>
          </button>
          <button class="action-btn" title="私信" @click.stop="emit('private-message', user.id)">
            <i class="action-icon">✉️</i>
            <span class="action-text">发送私信</span>
          </button>
          <!-- 房主可见的踢出按钮 -->
          <button v-if="isHost && user.id !== currentUserId" class="action-btn kick-btn" title="踢出房间" @click.stop="emit('kick-user', user.id)">
            <i class="action-icon">🚫</i>
            <span class="action-text">踢出房间</span>
          </button>
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
    
    <!-- 按钮区域 -->
    <div class="secret-chat-area" v-if="!gameStarted">
      <!-- Host: 房主按钮区 -->
      <div v-if="isHost" class="host-buttons">
        <!-- 准备游戏按钮 -->
        <button 
          class="ready-game-button" 
          @click="emit('toggle-ready')"
        >
          {{ isReady ? '取消准备' : '准备游戏' }}
        </button>
      </div>
      
      <!-- Non-Host: Ready/Cancel Button -->
      <button 
        v-else 
        class="ready-game-button" 
        @click="emit('toggle-ready')" 
      >
        {{ isReady ? '取消准备' : '准备游戏' }}
      </button>
      
       <!-- Secret Chat Button (shown only when game started) -->
       <button 
         v-if="gameStarted" 
         class="secret-chat-button" 
         @click="emit('toggle-secret-chat')" 
       >
         秘密聊天
       </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps({
  users: {
    type: Array,
    required: true,
    default: () => []
  },
  hostId: {
    type: String,
    required: true,
    default: ''
  },
  totalPlayers: {
    type: Number,
    required: true,
    default: 8
  },
  currentUserId: { 
    type: String,
    required: true,
    default: ''
  },
  readyUsers: {
    type: Array,
    required: true,
    default: () => []
  },
  gameStarted: {
    type: Boolean,
    required: true,
    default: false
  },
  isReady: {
    type: Boolean,
    required: true,
    default: false
  },
  isCollapsed: {
    type: Boolean,
    required: true,
    default: false
  },
  isHost: {
    type: Boolean,
    required: true
  }
});

const emit = defineEmits([
  'toggle-collapse', 
  'toggle-ready', 
  'toggle-secret-chat',
  'start-resize',
  'add-friend',
  'view-user-details',
  'private-message',
  'kick-user'
]);

// 添加过渡状态
const isTransitioning = ref(false);

// 处理折叠/展开带有动画效果
const handleToggleCollapse = () => {
  isTransitioning.value = true;
  
  // 延迟状态切换，让按钮先隐藏
  setTimeout(() => {
    emit('toggle-collapse');
    
    // 过渡完成后移除过渡状态
    setTimeout(() => {
      isTransitioning.value = false;
    }, 300); // 与CSS过渡时间匹配
  }, 150);
};

// 添加选中用户状态
const selectedUserId = ref(null);

// 切换显示用户操作按钮
const toggleActionButtons = (userId) => {
  if (selectedUserId.value === userId) {
    selectedUserId.value = null; // 如果已选中则隐藏
  } else {
    selectedUserId.value = userId; // 否则选中新用户
  }
};

// 添加点击文档其他位置关闭操作按钮的事件
const closeActionButtons = () => {
  selectedUserId.value = null;
};

// 在组件挂载时添加事件监听
onMounted(() => {
  document.addEventListener('click', (event) => {
    // 检查点击是否在用户列表外
    const usersList = document.querySelector('.users-list');
    if (usersList && !usersList.contains(event.target) && selectedUserId.value !== null) {
      closeActionButtons();
    }
  });
});

// 在组件卸载时移除事件监听
onBeforeUnmount(() => {
  document.removeEventListener('click', closeActionButtons);
});

const onAvatarError = (event) => {
  event.target.src = '/default_avatar.jpg';
};

</script>

<style scoped>
.users-container {
  width: 280px;
  background-color: white;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.3s ease;
  z-index: 1100; /* 修改为比倒计时遮罩更高的值，确保在遮罩之上 */
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

/* 调整大小手柄的视觉提示可以按需添加 */
/* .resize-handle::before { ... } */
/* .resize-handle:hover::before { ... } */

.users-container.collapsed {
  width: 60px !important; /* 添加!important确保折叠时覆盖inline style */
}

.users-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  padding: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.users-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
  white-space: nowrap; /* 防止折叠时文字换行 */
  overflow: hidden;
  flex: 1;
  margin-left: 10px;
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
  transition: opacity 0.15s ease;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background-color: #f0f0f0;
}

.transitioning .collapse-btn {
  opacity: 0;
}

.users-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 15px;
}

.user-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid #f9f9f9;
  cursor: pointer;
  position: relative;
  transition: background-color 0.2s ease;
  border-radius: 4px;
  margin-bottom: 2px;
}

.user-item:hover {
  background-color: #f5f5f5;
}

.user-avatar {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 10px;
  flex-shrink: 0;
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
  white-space: nowrap; /* 防止名字过长换行 */
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.ready-badge {
  background-color: #52c41a;
  color: white;
  font-size: 0.7rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 5px;
}

.user-divider {
  height: 1px;
  background-color: #e8e8e8;
  margin: 15px 0;
}

.ai-assistant .user-name {
  color: #1890ff;
}

/* 用户操作按钮样式 */
.user-actions {
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 6px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
  padding: 6px;
  position: absolute;
  left: 10px;
  top: 100%;
  transform: translateY(0);
  z-index: 5;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5%) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.action-btn {
  background: none;
  border: none;
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  margin: 2px 0;
  white-space: nowrap;
  color: #333;
}

.action-btn:hover {
  background-color: #f0f0f0;
}

.action-icon {
  font-size: 16px;
  line-height: 1;
  margin-right: 8px;
  width: 20px;
  text-align: center;
}

.action-text {
  font-size: 14px;
}

.kick-btn {
  color: #ff4d4f;
}

.kick-btn:hover {
  background-color: #fff1f0;
}

.secret-chat-area {
  padding: 15px;
  display: flex;
  justify-content: center;
  position: relative;
  z-index: 1000;
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
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
  position: relative; /* 为按钮也添加相对定位 */
  z-index: 1000; /* 默认按钮在遮罩下方 */
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
  margin: 0 auto;
  min-width: 260px;
  position: relative;
  z-index: 2000; /* 设置比遮罩层更高的值，确保按钮可见和可点击 */
}

.ready-game-button:hover {
  background-color: #218838;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

/* Ready indicator style */
.ready-badge {
  background-color: #52c41a; /* Green */
  color: white;
  font-size: 0.7rem;
  padding: 1px 5px;
  border-radius: 4px;
  margin-left: 6px;
  vertical-align: middle;
}
</style> 