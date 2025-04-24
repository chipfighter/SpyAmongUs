<template>
  <Teleport to="body">
    <div class="inquiry-overlay" v-show="visible" :class="{ 'fade-out': !visible }">
      <div class="inquiry-modal" :class="{ 'slide-out': !visible }">
        <!-- 上帝角色Emoji装饰 -->
        <div class="god-emoji">👑</div>
        
        <!-- 标题 -->
        <h2 class="modal-title">成为上帝</h2>
        
        <!-- 询问消息 -->
        <div class="inquiry-message">
          {{ message }}
        </div>
        
        <!-- 倒计时进度条 -->
        <div class="countdown-bar-container">
          <div class="countdown-bar" :style="{ width: `${timePercentage}%` }"></div>
        </div>
        <div class="countdown-text">{{ displayTimeRemaining }}秒</div>
        
        <!-- 按钮区域 -->
        <div class="button-container">
          <button class="decline-button" @click="handleDecline">
            <span class="emoji">🙅</span> 拒绝
          </button>
          <button class="accept-button" @click="handleAccept">
            <span class="emoji">🙋</span> 同意
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  message: {
    type: String,
    default: '您愿意担任本局游戏的上帝吗？'
  },
  timeout: {
    type: Number,
    default: 10 // 默认10秒倒计时
  }
});

const emit = defineEmits(['accept', 'decline', 'timeout']);

// 计时相关状态
const timeRemaining = ref(props.timeout);
const intervalId = ref(null);

// 计算倒计时百分比
const timePercentage = computed(() => {
  return (timeRemaining.value / props.timeout) * 100;
});

// 计算用于显示的倒计时时间（只显示整数部分）
const displayTimeRemaining = computed(() => {
  return Math.ceil(timeRemaining.value);
});

// 当弹窗显示时开始倒计时
watch(() => props.visible, (newVal) => {
  if (newVal) {
    startCountdown();
  } else {
    stopCountdown();
  }
});

// 开始倒计时
const startCountdown = () => {
  // 重置计时器
  timeRemaining.value = props.timeout;
  
  // 清除可能存在的旧计时器
  if (intervalId.value) {
    clearInterval(intervalId.value);
  }
  
  // 创建新计时器
  intervalId.value = setInterval(() => {
    timeRemaining.value -= 0.1; // 每0.1秒减少0.1
    
    // 倒计时结束
    if (timeRemaining.value <= 0) {
      stopCountdown();
      emit('timeout');
    }
  }, 100); // 100毫秒更新一次，使进度条更平滑
};

// 停止倒计时
const stopCountdown = () => {
  if (intervalId.value) {
    clearInterval(intervalId.value);
    intervalId.value = null;
  }
};

// 处理同意按钮点击
const handleAccept = () => {
  stopCountdown();
  emit('accept');
};

// 处理拒绝按钮点击
const handleDecline = () => {
  stopCountdown();
  emit('decline');
};

// 组件销毁前清理计时器
onBeforeUnmount(() => {
  stopCountdown();
});
</script>

<style scoped>
.inquiry-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1500;
  animation: fadeIn 0.3s ease;
  transition: opacity 0.3s ease;
}

.inquiry-overlay.fade-out {
  opacity: 0;
}

.inquiry-modal {
  width: 450px;
  background-color: #fff;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  position: relative;
  text-align: center;
  animation: slideIn 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
  transition: transform 0.3s cubic-bezier(0.22, 0.61, 0.36, 1), opacity 0.3s ease;
}

.inquiry-modal.slide-out {
  transform: translateY(-50px);
  opacity: 0;
}

.god-emoji {
  font-size: 64px;
  margin-bottom: 16px;
  animation: float 3s ease-in-out infinite;
  text-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.modal-title {
  font-size: 28px;
  margin: 0 0 20px;
  color: #333;
}

.inquiry-message {
  font-size: 18px;
  margin-bottom: 25px;
  color: #666;
  line-height: 1.5;
}

.countdown-bar-container {
  width: 100%;
  height: 10px;
  background-color: #f0f0f0;
  border-radius: 5px;
  overflow: hidden;
  margin-bottom: 10px;
}

.countdown-bar {
  height: 100%;
  background: linear-gradient(90deg, #FFD700, #FFA500);
  border-radius: 5px;
  transition: width 0.1s linear;
}

.countdown-text {
  font-size: 14px;
  color: #888;
  margin-bottom: 25px;
}

.button-container {
  display: flex;
  justify-content: space-between;
  gap: 15px;
}

.accept-button, .decline-button {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.accept-button {
  background-color: #4CAF50;
  color: white;
}

.accept-button:hover {
  background-color: #45a049;
  transform: translateY(-2px);
}

.decline-button {
  background-color: #f44336;
  color: white;
}

.decline-button:hover {
  background-color: #e53935;
  transform: translateY(-2px);
}

.emoji {
  font-size: 20px;
  margin-right: 8px;
}

/* 动画 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideIn {
  from { 
    transform: translateY(-50px);
    opacity: 0;
  }
  to { 
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes float {
  0% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
  100% { transform: translateY(0px); }
}
</style> 