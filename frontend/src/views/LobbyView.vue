<template>
  <div class="lobby-container">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="action-buttons">
        <button class="create-room-btn">
          <i class="icon">+</i> 创建房间
        </button>
        <button class="join-room-btn">
          <i class="icon">→</i> 加入房间
        </button>
      </div>
      
      <div class="logo">谁是卧底</div>
      
      <div class="user-info">
        <span class="username">{{ userStore.user?.username || '未登录' }}</span>
        <div class="avatar-container">
          <img :src="userStore.userAvatar" alt="用户头像" class="avatar" />
        </div>
        <button @click="handleLogout" class="logout-btn" title="登出">
          退出
        </button>
      </div>
    </header>
    
    <!-- 大厅内容区 -->
    <main class="lobby-content">
      <h2 class="section-title">游戏大厅</h2>
      
      <!-- 空状态 -->
      <div class="empty-state">
        <div class="empty-icon">🏠</div>
        <h3>暂无公开房间</h3>
        <p>点击顶部按钮创建或加入房间</p>
      </div>
      
      <!-- 房间列表 - 当有房间时会显示 -->
      <div class="room-list" style="display: none;">
        <div class="room-card">
          <div class="room-header">
            <h3 class="room-name">欢乐谁是卧底</h3>
            <span class="room-status">等待中</span>
          </div>
          <div class="room-info">
            <div class="room-host">房主: 张三</div>
            <div class="room-players">2/8 人</div>
          </div>
          <button class="join-room-card-btn">加入房间</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/userStore'

const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  // 初始化用户数据
  userStore.initStore()
  
  // 如果没有登录则跳转到登录页
  if (!userStore.isAuthenticated) {
    router.push('/login')
  }
})

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.lobby-container {
  min-height: 100vh;
  background-color: #f5f7fa;
  display: flex;
  flex-direction: column;
}

/* 顶部导航栏 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: white;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
  color: #3b71ca;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.create-room-btn, .join-room-btn {
  padding: 0.6rem 1rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border: none;
  border-radius: 4px;
  transition: all 0.2s;
}

.create-room-btn {
  background-color: #3b71ca;
  color: white;
}

.create-room-btn:hover {
  background-color: #2e5da3;
}

.join-room-btn {
  background-color: #28a745;
  color: white;
}

.join-room-btn:hover {
  background-color: #218838;
}

.icon {
  font-style: normal;
  font-weight: bold;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.username {
  font-weight: bold;
  color: #495057;
}

.avatar-container {
  position: relative;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #e9ecef;
}

.logout-btn {
  background-color: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.4rem 0.9rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background-color: #c82333;
}

/* 大厅内容区 */
.lobby-content {
  flex: 1;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.section-title {
  color: #495057;
  margin-bottom: 2rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #e9ecef;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem 1rem;
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.empty-state h3 {
  font-size: 1.5rem;
  color: #495057;
  margin-bottom: 0.5rem;
}

.empty-state p {
  color: #6c757d;
}

/* 房间列表 */
.room-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.room-card {
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  padding: 1.5rem;
  transition: transform 0.2s;
}

.room-card:hover {
  transform: translateY(-5px);
}

.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.room-name {
  font-size: 1.2rem;
  color: #495057;
  margin: 0;
}

.room-status {
  background-color: #28a745;
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  font-size: 0.8rem;
}

.room-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.join-room-card-btn {
  width: 100%;
  background-color: #3b71ca;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.6rem;
  font-weight: bold;
  cursor: pointer;
  transition: background-color 0.2s;
}

.join-room-card-btn:hover {
  background-color: #2e5da3;
}

@media (max-width: 768px) {
  .header {
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
  }
  
  .logo {
    position: static;
    transform: none;
    order: -1;
  }
  
  .action-buttons {
    width: 100%;
  }
  
  .create-room-btn, .join-room-btn {
    flex: 1;
  }
  
  .user-info {
    width: 100%;
    justify-content: space-between;
  }
}
</style>