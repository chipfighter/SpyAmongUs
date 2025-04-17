<template>
  <div class="users-container" :class="{ 'collapsed': isCollapsed }">
    <div class="resize-handle" @mousedown="emit('start-resize', $event)"></div>
    <div class="users-header">
      <h3>玩家列表 ({{ users.length }}/{{ totalPlayers || 8 }})</h3>
      <button class="collapse-btn" @click="emit('toggle-collapse')">
        {{ isCollapsed ? '◀' : '▶' }}
      </button>
    </div>
    
    <div class="users-list">
      <!-- 真实用户 -->
      <div v-for="user in users" :key="user.id" class="user-item">
        <div class="user-avatar">
          <img :src="user.avatar_url || '/default_avatar.jpg'" alt="用户头像" @error="onAvatarError">
          <span v-if="user.id === hostId" class="host-badge">房主</span>
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
    
    <!-- 按钮区域 -->
    <div class="secret-chat-area">
      <button 
        v-if="gameStarted" 
        class="secret-chat-button" 
        @click="emit('toggle-secret-chat')" 
      >
        秘密聊天
      </button>
      <button 
        v-else 
        class="ready-game-button" 
        @click="emit('toggle-ready')" 
      >
        {{ isReady ? '取消准备' : '准备游戏' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue';

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
  currentUserId: { // 虽然模板没直接用，但可能未来逻辑需要
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
  }
});

const emit = defineEmits([
  'toggle-collapse', 
  'toggle-ready', 
  'toggle-secret-chat',
  'start-resize' 
]);

// 处理头像加载失败
const onAvatarError = (event) => {
  event.target.src = '/default_avatar.jpg'; // 设置为默认头像
};

// 注意：原 RoomView 中的 toggleUserList, toggleReady, toggleSecretChat, startResizing
// 这些方法现在需要在父组件(RoomView)中实现，并由本组件通过 emit 触发。
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
  white-space: nowrap; /* 防止折叠时文字换行 */
  overflow: hidden;
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
  flex-shrink: 0; /* 防止按钮被挤压 */
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

.secret-chat-area {
  padding: 15px;
  display: flex;
  justify-content: center;
  border-top: 1px solid #f0f0f0; /* 添加顶部边框 */
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
</style> 