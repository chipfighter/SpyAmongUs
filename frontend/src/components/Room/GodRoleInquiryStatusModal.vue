<template>
  <Teleport to="body">
    <div class="status-overlay" v-show="visible" :class="{ 'fade-out': !visible }">
      <div class="status-modal" :class="{ 'slide-out': !visible }">
        <!-- 装饰Emoji -->
        <div class="status-emoji">👑 ⏳</div>
        
        <!-- 标题 -->
        <h2 class="modal-title">上帝角色询问中</h2>
        
        <!-- 消息内容 -->
        <div class="status-message">
          {{ message }}
        </div>
        
        <!-- 倒计时条 -->
        <div class="countdown-bar-container">
          <div class="countdown-bar" :style="{ width: `${timePercentage}%` }"></div>
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
    default: '正在询问玩家是否愿意担任上帝，请稍候...'
  },
  timeout: {
    type: Number,
    default: 7 // 默认7秒倒计时
  },
  username: {
    type: String,
    default: ''
  }
});

// 计时相关状态
const timeRemaining = ref(props.timeout);
const intervalId = ref(null);

// 计算倒计时百分比
const timePercentage = computed(() => {
  return (timeRemaining.value / props.timeout) * 100;
});

// 格式化消息内容
const formattedMessage = computed(() => {
  if (props.username) {
    return `正在询问 ${props.username} 是否愿意担任上帝...`;
  }
  return props.message;
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
    
    // 倒计时结束（不需要处理，由父组件控制弹窗关闭）
    if (timeRemaining.value <= 0) {
      stopCountdown();
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

// 组件销毁前清理计时器
onBeforeUnmount(() => {
  stopCountdown();
});
</script>

<style scoped>
.status-overlay {
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

.status-overlay.fade-out {
  opacity: 0;
}

.status-modal {
  width: 400px;
  background-color: #fff;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  position: relative;
  text-align: center;
  animation: slideIn 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
  transition: transform 0.3s cubic-bezier(0.22, 0.61, 0.36, 1), opacity 0.3s ease;
}

.status-modal.slide-out {
  transform: translateY(-50px);
  opacity: 0;
}

.status-emoji {
  font-size: 48px;
  margin-bottom: 16px;
  animation: float 3s ease-in-out infinite;
  text-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.modal-title {
  font-size: 24px;
  margin: 0 0 15px;
  color: #333;
}

.status-message {
  font-size: 18px;
  margin-bottom: 30px;
  color: #666;
  line-height: 1.5;
}

.countdown-bar-container {
  width: 100%;
  height: 10px;
  background-color: #f0f0f0;
  border-radius: 5px;
  overflow: hidden;
}

.countdown-bar {
  height: 100%;
  background: linear-gradient(90deg, #FFD700, #FFA500);
  border-radius: 5px;
  transition: width 0.1s linear;
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