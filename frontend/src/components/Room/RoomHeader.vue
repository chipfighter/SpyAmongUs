<template>
  <div class="room-header">
    <div class="room-title">
      <h1>{{ roomInfo.name }}</h1>
      <div class="room-code">
        邀请码: {{ roomInfo.invite_code }}
        <button class="copy-button" @click="$emit('copy-invite-code')" title="复制邀请码">📋</button>
      </div>
    </div>
    <div class="connection-status" :class="connectionStatus">
      <span v-if="connectionStatus === 'connected'" title="连接正常">🟢</span>
      <span v-else-if="connectionStatus === 'connecting'" title="正在连接">🟡</span>
      <span v-else title="连接已断开">🔴</span>
    </div>
    <!-- 只在游戏未开始且不在上帝轮询阶段时显示按钮 -->
    <div class="room-actions" v-if="!gameStarted && !isGodPolling">
      <button 
        class="back-to-lobby-button" 
        @click="$emit('back-to-lobby')"
        title="返回大厅(保持在房间内)"
      >
        返回大厅
      </button>
      <!-- 普通用户退出按钮 -->
      <button 
        v-if="!isHost" 
        class="exit-button" 
        @click="$emit('leave-room')"
      >
        退出房间
      </button>
      <!-- 房主专属按钮 -->
      <template v-if="isHost">
        <button 
          class="exit-button host-leave" 
          @click="$emit('leave-room')" 
          title="退出房间并将房主移交给下一位玩家"
        >
          退出房间(移交)
        </button>
        <button 
          class="exit-button host-disband" 
          @click="$emit('disband-room')"
          style="margin-left: 8px;"
        >
          解散房间
        </button>
      </template>
    </div>
    <!-- 游戏状态指示器 -->
    <div v-else class="game-status-indicator">
      {{ isGodPolling ? '选择上帝中...' : '游戏进行中' }}
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue';

defineProps({
  roomInfo: {
    type: Object,
    required: true,
    default: () => ({ name: '', invite_code: '' })
  },
  connectionStatus: {
    type: String,
    required: true,
    default: 'disconnected'
  },
  isHost: {
    type: Boolean,
    required: true,
    default: false
  },
  // 添加游戏状态属性
  gameStarted: {
    type: Boolean,
    default: false
  },
  // 添加上帝轮询状态属性
  isGodPolling: {
    type: Boolean,
    default: false
  }
});

defineEmits([
  'copy-invite-code',
  'back-to-lobby',
  'leave-room', 
  'disband-room'
]);

</script>

<style scoped>
.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background-color: white;
  border-bottom: 1px solid #e0e0e0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1000; /* 设置为和遮罩相同的值，这样容器本身不会显示 */
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

.room-actions {
  position: relative;
  z-index: 1000; /* 设置为和遮罩相同的值，这样容器本身不会显示 */
}

/* 退出房间按钮样式 */
.exit-button {
  padding: 8px 16px;
  background-color: #eaeaea;
  border: none;
  border-radius: 4px;
  color: #333;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  z-index: 2000; /* 设置比遮罩层更高的值，确保按钮可见和可点击 */
}

.exit-button:hover {
  background-color: #e0e0e0;
}

/* 房主退出(移交)按钮样式 */
.exit-button.host-leave {
  background-color: #FFA726; /* 橙色 */
  color: white;
  position: relative;
  z-index: 2000; /* 设置比遮罩层更高的值，确保按钮可见和可点击 */
}

.exit-button.host-leave:hover {
  background-color: #FFB74D;
}

/* 房主解散房间按钮样式 */
.exit-button.host-disband {
  background-color: #EF5350; /* 红色 */
  color: white;
  margin-left: 8px;
  position: relative;
  z-index: 2000; /* 设置比遮罩层更高的值，确保按钮可见和可点击 */
}

/* 返回大厅按钮样式 */
.back-to-lobby-button {
  padding: 8px 16px;
  background-color: #1890ff;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  transition: all 0.3s;
  margin-right: 10px; /* 保持与退出按钮的间距 */
  position: relative;
  z-index: 1000; /* 确保在倒计时遮罩下方，不可点击 */
}

.back-to-lobby-button:hover {
  background-color: #40a9ff;
}

.actions-area {
  display: flex;
  align-items: center;
  position: relative;
  z-index: 2001; /* 确保按钮在最上层 */
}

.host-exit { 
  background-color: #ff4d4f;
  color: white;
}

.host-exit:hover {
  background-color: #ff7875;
}

.exit-button.host-disband:hover {
  background-color: #E57373;
}

/* 游戏状态指示器样式 */
.game-status-indicator {
  padding: 8px 16px;
  background-color: #1890ff;
  border-radius: 4px;
  color: white;
  font-weight: bold;
  text-align: center;
}
</style> 