<template>
  <div class="room-header">
    <div class="room-title">
      <h1>{{ roomInfo.name }}</h1>
      <div class="room-code">
        邀请码: {{ roomInfo.invite_code }}
        <button class="copy-button" @click="$emit('copy-invite-code')" title="复制邀请码">📋</button>
      </div>
    </div>
    <!-- 游戏回合显示（居中） -->
    <div v-if="gameStarted" class="game-round-container">
      <div class="game-round">回合 {{ currentRound }}</div>
    </div>
    
    <!-- 词语显示（右侧） -->
    <div v-if="gameStarted && roomStore.currentRole" class="word-display-container">
      <!-- 上帝视角：显示两个词语 -->
      <template v-if="roomStore.currentRole === 'god'">
        <div class="god-words">
          <div class="word-item">卧底词语：{{ roomStore.spyWord }}</div>
          <div class="word-item">平民词语：{{ roomStore.civilianWord }}</div>
        </div>
      </template>
      
      <!-- 平民视角：只显示平民词语 -->
      <div v-else-if="roomStore.currentRole === 'civilian'" class="word-item">
        平民词语：{{ roomStore.civilianWord }}
      </div>
      
      <!-- 卧底视角：只显示卧底词语 -->
      <div v-else-if="roomStore.currentRole === 'spy'" class="word-item">
        卧底词语：{{ roomStore.spyWord }}
      </div>
    </div>
    
    <div class="connection-status" :class="connectionStatus">
      <span v-if="connectionStatus === 'connected'" title="连接正常">🟢</span>
      <span v-else-if="connectionStatus === 'connecting'" title="正在连接">🟡</span>
      <span v-else title="连接已断开">🔴</span>
    </div>
    <!-- 只在游戏未开始且不在上帝轮询阶段时显示按钮 -->
    <div class="room-actions" v-if="!gameStarted && !isGodPolling">
      <!-- 所有用户的返回大厅按钮 -->
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
    <!-- 游戏状态指示器（右上角） -->
    <div v-else class="game-status-indicator" :class="isGodPolling ? 'god-polling' : gamePhaseClass">
      {{ isGodPolling ? '选择上帝中...' : gamePhaseText }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoomStore } from '../../stores/room';

const roomStore = useRoomStore();

const props = defineProps({
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
  },
  // 添加游戏阶段属性
  gamePhase: {
    type: String,
    default: 'speaking'
  },
  // 添加当前回合属性
  currentRound: {
    type: Number,
    default: 1
  }
});

// 根据游戏阶段返回对应的文本
const gamePhaseText = computed(() => {
  switch(props.gamePhase) {
    case 'speaking':
      return '发言中...';
    case 'voting':
      return '投票中';
    case 'secret_chat':
      return '秘密聊天室';
    case 'last_words':
      return '遗言时间';
    default:
      return '游戏中';
  }
});

// 根据游戏阶段返回对应的CSS类名
const gamePhaseClass = computed(() => {
  switch(props.gamePhase) {
    case 'speaking':
      return 'phase-speaking';
    case 'voting':
      return 'phase-voting';
    case 'secret_chat':
      return 'phase-secret-chat';
    case 'last_words':
      return 'phase-last-words';
    default:
      return '';
  }
});
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
  max-width: 40%;
}

.room-title h1 {
  margin: 0;
  font-size: 1.5rem;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

/* 游戏回合显示样式 */
.game-round-container {
  position: absolute;
  top: 5px; /* 向上移动，与顶部边框保持5px的距离 */
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1001;
}

.game-round {
  font-weight: bold;
  font-size: 1.8rem;
  color: #333;
  text-shadow: 0 1px 2px rgba(0,0,0,0.1);
  background-color: rgba(255,255,255,0.7);
  padding: 2px 15px;
  border-radius: 15px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.1);
  transition: all 0.3s ease;
}

/* 词语显示样式 - 移至右侧 */
.word-display-container {
  position: absolute;
  top: 50%;
  right: 180px; /* 与右侧保持一定距离 */
  transform: translateY(-50%); /* 垂直居中 */
  background-color: rgba(255,255,255,0.85);
  padding: 5px 12px;
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  font-weight: 500;
  max-width: 450px;
  max-height: 45px; /* 确保不超过顶栏高度 */
  overflow: hidden;
  z-index: 1002;
}

.word-item {
  margin: 2px 0;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
}

.god-words {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 20px; /* 两个词之间的间距 */
}

/* 游戏状态指示器样式 */
.game-status-indicator {
  padding: 8px 16px;
  border-radius: 4px;
  color: white;
  font-weight: bold;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* 上帝轮询状态 */
.game-status-indicator.god-polling {
  background-color: #1890ff;
}

/* 不同阶段的样式 - 游戏状态指示器 */
.game-status-indicator.phase-speaking {
  background-color: #64B5F6; /* 浅蓝色 */
}

.game-status-indicator.phase-voting {
  background-color: #81C784; /* 浅绿色 */
}

.game-status-indicator.phase-secret-chat {
  background-color: #9575CD; /* 浅紫色 */
}

.game-status-indicator.phase-last-words {
  background-color: #9E9E9E; /* 灰色 */
}
</style> 