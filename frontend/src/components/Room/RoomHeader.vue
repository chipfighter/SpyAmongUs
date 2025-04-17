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
    <div class="room-actions">
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

.host-exit { /* 这个类名似乎没用到，但保留以防万一 */
  background-color: #ff4d4f;
  color: white;
}

.host-exit:hover { /* 这个类名似乎没用到 */
  background-color: #ff7875;
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
  /* margin-left: 8px;  <-- 之前的行内样式现在移到这里 */
}

.exit-button.host-disband:hover {
  background-color: #E57373;
}

/* 返回大厅按钮样式 (从 RoomView.vue 迁移) */
.back-to-lobby-button {
  padding: 8px 16px;
  background-color: #1890ff;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  transition: all 0.3s;
  margin-right: 10px; /* 保持与退出按钮的间距 */
}

.back-to-lobby-button:hover {
  background-color: #40a9ff;
}

</style> 