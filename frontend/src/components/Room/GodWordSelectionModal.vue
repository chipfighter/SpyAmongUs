<template>
  <Teleport to="body">
    <div class="selection-overlay" v-show="visible" :class="{ 'fade-out': !visible }">
      <div class="selection-modal" :class="{ 'slide-out': !visible }">
        <!-- 上帝角色Emoji装饰 -->
        <div class="god-emoji">👑 🎮 🎯 🎪</div>
        
        <!-- 标题 -->
        <h2 class="modal-title">选择词语</h2>
        
        <!-- 提示消息 -->
        <div class="selection-message">
          {{ message }}
        </div>
        
        <!-- 倒计时 -->
        <div class="countdown-text">倒计时: {{ displayTimeRemaining }}秒</div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="team-input">
            <h3>平民词语 (最多5个字)</h3>
            <input 
              v-model="teamOneWord" 
              placeholder="请输入平民词语" 
              maxlength="5"
              class="word-input"
            />
          </div>
          
          <div class="team-input">
            <h3>卧底词语 (最多5个字)</h3>
            <input 
              v-model="teamTwoWord" 
              placeholder="请输入卧底词语" 
              maxlength="5"
              class="word-input"
            />
          </div>
        </div>
        
        <!-- 倒计时进度条 -->
        <div class="countdown-bar-container">
          <div class="countdown-bar" :style="{ width: `${timePercentage}%` }"></div>
        </div>
        
        <!-- 确认按钮 -->
        <button 
          class="confirm-button" 
          @click="handleConfirm"
          :disabled="!isValid"
        >
          确认
        </button>
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
    default: '请选择双方词语。'
  },
  timeout: {
    type: Number,
    default: 30 // 默认30秒倒计时
  }
});

const emit = defineEmits(['confirm', 'timeout']);

// 计时相关状态
const timeRemaining = ref(props.timeout);
const intervalId = ref(null);

// 输入相关状态 - 只有两个词
const teamOneWord = ref('');
const teamTwoWord = ref('');

// 验证输入是否有效 - 两个词都不能为空
const isValid = computed(() => {
  return teamOneWord.value.trim() !== '' && teamTwoWord.value.trim() !== '';
});

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
    // 清空之前的输入
    teamOneWord.value = '';
    teamTwoWord.value = '';
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

// 处理确认按钮点击
const handleConfirm = () => {
  if (!isValid.value) return;
  
  stopCountdown();
  emit('confirm', {
    teamOne: [teamOneWord.value.trim()],
    teamTwo: [teamTwoWord.value.trim()]
  });
};

// 组件销毁前清理计时器
onBeforeUnmount(() => {
  stopCountdown();
});
</script>

<style scoped>
.selection-overlay {
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

.selection-overlay.fade-out {
  opacity: 0;
}

.selection-modal {
  width: 500px;
  background-color: #fff;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  position: relative;
  text-align: center;
  animation: slideIn 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
  transition: transform 0.3s cubic-bezier(0.22, 0.61, 0.36, 1), opacity 0.3s ease;
}

.selection-modal.slide-out {
  transform: translateY(-50px);
  opacity: 0;
}

.god-emoji {
  font-size: 40px;
  margin-bottom: 16px;
  animation: float 3s ease-in-out infinite;
  text-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.modal-title {
  font-size: 28px;
  margin: 0 0 15px;
  color: #333;
}

.selection-message {
  font-size: 16px;
  margin-bottom: 15px;
  color: #666;
  line-height: 1.5;
}

.countdown-text {
  font-size: 16px;
  color: #444;
  margin-bottom: 20px;
  font-weight: bold;
}

.input-area {
  margin-bottom: 20px;
}

.team-input {
  margin-bottom: 15px;
  text-align: left;
}

.team-input h3 {
  font-size: 16px;
  margin: 0 0 8px;
  color: #333;
}

.word-input {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s ease;
  text-align: center;
  font-size: 16px;
}

.word-input:focus {
  border-color: #4CAF50;
  outline: none;
}

.countdown-bar-container {
  width: 100%;
  height: 8px;
  background-color: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 20px;
}

.countdown-bar {
  height: 100%;
  background: linear-gradient(90deg, #FFD700, #FFA500);
  border-radius: 4px;
  transition: width 0.1s linear;
}

.confirm-button {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 8px;
  background-color: #4CAF50;
  color: white;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s ease;
}

.confirm-button:hover:not(:disabled) {
  background-color: #45a049;
  transform: translateY(-2px);
}

.confirm-button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
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