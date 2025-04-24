<template>
  <Teleport to="body">
    <div class="game-loading-overlay" v-if="visible">
      <div class="loading-container">
        <!-- 动画元素 -->
        <div class="loading-animation">
          <div class="spinner"></div>
          <div class="card-icons">
            <span class="card-icon">🎮</span>
            <span class="card-icon">🎯</span>
            <span class="card-icon">🎭</span>
          </div>
        </div>
        
        <!-- 加载文本 -->
        <h2 class="loading-title">{{ title }}</h2>
        <p class="loading-message">{{ message }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '游戏初始化中'
  },
  message: {
    type: String,
    default: '正在准备游戏环境，请稍候...'
  }
});
</script>

<style scoped>
.game-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
  animation: fadeIn 0.3s ease;
}

.loading-container {
  background-color: white;
  padding: 30px;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  max-width: 400px;
  width: 90%;
  animation: scaleIn 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.loading-animation {
  position: relative;
  height: 100px;
  margin-bottom: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.spinner {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  border: 6px solid #f3f3f3;
  border-top: 6px solid #4CAF50;
  border-right: 6px solid #2196F3;
  border-bottom: 6px solid #FF9800;
  border-left: 6px solid #f44336;
  animation: spin 1.5s linear infinite;
}

.card-icons {
  position: absolute;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.card-icon {
  font-size: 24px;
  margin: 0 10px;
  opacity: 0.8;
  animation: float 3s ease-in-out infinite;
  animation-delay: calc(var(--i, 0) * 0.5s);
}

.card-icon:nth-child(1) {
  --i: 0;
}

.card-icon:nth-child(2) {
  --i: 1;
}

.card-icon:nth-child(3) {
  --i: 2;
}

.loading-title {
  margin: 0 0 10px 0;
  font-size: 24px;
  color: #333;
  font-weight: bold;
}

.loading-message {
  margin: 0;
  color: #666;
  font-size: 16px;
  line-height: 1.5;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

@keyframes float {
  0% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
  100% { transform: translateY(0); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes scaleIn {
  from { 
    transform: scale(0.9);
    opacity: 0;
  }
  to { 
    transform: scale(1);
    opacity: 1;
  }
}
</style> 