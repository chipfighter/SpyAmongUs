<template>
  <div class="countdown-overlay" v-if="isVisible">
    <div class="countdown-content">
      <div v-if="currentCount > 0" class="countdown-number" :class="'count-' + currentCount">
        {{ currentCount }}
      </div>
      <div v-else class="countdown-text">游戏开始！</div>
      
      <!-- 添加取消准备按钮，只在倒计时数字显示时显示 -->
      <button 
        v-if="currentCount > 0" 
        class="cancel-ready-button" 
        @click="$emit('cancel-ready')"
      >
        取消准备
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue';

const isVisible = ref(false);
const currentCount = ref(3);
let countdownTimer = null;

const emit = defineEmits(['cancel-ready']);

// 开始倒计时
const startCountdown = (duration = 5) => {
  isVisible.value = true;
  currentCount.value = 3;
  
  countdownTimer = setInterval(() => {
    currentCount.value--;
    
    if (currentCount.value < 0) {
      clearInterval(countdownTimer);
      
      // 显示"游戏开始"几秒后隐藏
      setTimeout(() => {
        isVisible.value = false;
      }, 1500);
    }
  }, 1000);
};

// 取消倒计时
const cancelCountdown = () => {
  console.log('CountdownOverlay: 取消倒计时动画');
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  // 立即隐藏倒计时组件
  isVisible.value = false;
  // 重置计数器
  currentCount.value = 3;
};

// 组件卸载时清理
onBeforeUnmount(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer);
  }
});

// 将方法暴露给父组件
defineExpose({
  startCountdown,
  cancelCountdown
});
</script>

<style scoped>
.countdown-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1500; /* 设置较高层级覆盖大部分UI */
  animation: fadeIn 0.3s ease-in-out;
  pointer-events: auto; /* 确保遮罩可以接收点击事件，阻止点击下方元素 */
}

.countdown-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none; /* 确保倒计时内容不会拦截事件 */
}

.countdown-number {
  font-size: 150px;
  font-weight: bold;
  color: white;
  text-shadow: 0 0 15px rgba(255, 255, 255, 0.7), 0 0 30px rgba(255, 255, 255, 0.5);
}

/* 为每个数字单独设置不同的动画 */
.count-3 {
  animation: impactThree 0.5s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
}

.count-2 {
  animation: impactTwo 0.5s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
}

.count-1 {
  animation: impactOne 0.5s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
}

/* 数字3的动画：从大到小拍打 */
@keyframes impactThree {
  0% {
    transform: scale(3.5);
    opacity: 0;
  }
  35% {
    transform: scale(1.4);
    opacity: 1;
  }
  65% {
    transform: scale(0.85);
  }
  100% {
    transform: scale(1);
  }
}

/* 数字2的动画：从大到小拍打，略有不同 */
@keyframes impactTwo {
  0% {
    transform: scale(4);
    opacity: 0;
  }
  40% {
    transform: scale(1.5);
    opacity: 1;
  }
  70% {
    transform: scale(0.8);
  }
  100% {
    transform: scale(1);
  }
}

/* 数字1的动画：从大到小拍打，更加强烈 */
@keyframes impactOne {
  0% {
    transform: scale(5);
    opacity: 0;
  }
  30% {
    transform: scale(1.8);
    opacity: 1;
  }
  60% {
    transform: scale(0.75);
  }
  85% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
  }
}

.countdown-text {
  font-size: 60px;
  font-weight: bold;
  color: white;
  text-shadow: 0 0 15px rgba(255, 255, 255, 0.7), 0 0 30px rgba(255, 255, 255, 0.5);
  animation: bounceIn 0.8s ease;
}

@keyframes bounceIn {
  0% {
    transform: scale(0.3);
    opacity: 0;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.8;
  }
  70% { transform: scale(0.9); }
  100% { transform: scale(1); opacity: 1; }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 取消准备按钮样式 */
.cancel-ready-button {
  margin-top: 50px;
  padding: 12px 30px;
  background-color: rgba(255, 77, 79, 0.5); /* 更透明 */
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 18px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(2px);
  pointer-events: auto !important; /* 确保按钮可点击，优先级最高 */
  position: relative; /* 创建新的层叠上下文 */
  z-index: 10; /* 确保在倒计时内容之上 */
}

.cancel-ready-button:hover {
  background-color: rgba(255, 77, 79, 0.9);
  transform: translateY(-3px);
  box-shadow: 0 5px 20px rgba(255, 255, 255, 0.5);
}
</style> 