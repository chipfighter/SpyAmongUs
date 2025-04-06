<template>
  <div class="user-list-container">
    <h3 class="user-list-title">玩家列表</h3>
    <div v-if="loading" class="loading">加载中...</div>
    <ul v-else class="user-list">
      <li v-for="user in users" :key="user.id" class="user-item" :class="{ 'current-user': user.id === currentUserId }">
        <div class="user-avatar" :style="avatarStyle(user)"></div>
        <div class="user-info">
          <span class="user-name">{{ user.username }}</span>
          <span v-if="user.is_host || user.id === hostId" class="host-badge">房主</span>
          <span v-if="user.id === currentUserId" class="self-badge">我</span>
        </div>
        <div class="user-status">
          {{ user.status || '在线' }}
        </div>
      </li>
      <li v-if="users.length < maxPlayers" class="user-item empty">
        <div class="waiting-slot">等待玩家加入...</div>
      </li>
    </ul>
    <div class="user-count">{{ users.length }}/{{ maxPlayers }} 玩家</div>
  </div>
</template>

<script>
import { computed, ref } from 'vue'
import { userStore } from '../store/user'

export default {
  name: 'UserList',
  
  props: {
    users: {
      type: Array,
      default: () => []
    },
    hostId: {
      type: String,
      default: ''
    },
    maxPlayers: {
      type: Number,
      default: 8
    },
    loading: {
      type: Boolean,
      default: false
    }
  },
  
  setup() {
    // 当前用户ID
    const currentUserId = computed(() => userStore.user?.id || '')
    
    // 默认头像颜色
    const avatarColors = [
      '#FF5722', '#E91E63', '#9C27B0', '#673AB7', 
      '#3F51B5', '#2196F3', '#03A9F4', '#00BCD4',
      '#009688', '#4CAF50', '#8BC34A', '#CDDC39'
    ]
    
    // 生成头像样式
    const avatarStyle = (user) => {
      if (user.avatar && user.avatar.startsWith('http')) {
        // 使用提供的头像URL
        return {
          backgroundImage: `url(${user.avatar})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center'
        }
      } else {
        // 生成一个基于用户ID的随机颜色
        const colorIndex = user.id ? Math.abs(user.id.charCodeAt(0) % avatarColors.length) : 0
        const bgColor = avatarColors[colorIndex]
        const initials = user.username ? user.username.charAt(0).toUpperCase() : '?'
        
        return {
          backgroundColor: bgColor,
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1.2rem',
          fontWeight: 'bold',
          '::before': {
            content: `"${initials}"`
          }
        }
      }
    }
    
    return {
      currentUserId,
      avatarStyle
    }
  }
}
</script>

<style scoped>
.user-list-container {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  padding: 1rem;
  margin-bottom: 1rem;
}

.user-list-title {
  font-size: 1.1rem;
  margin: 0 0 1rem 0;
  color: #333;
  text-align: center;
}

.loading {
  text-align: center;
  padding: 1rem;
  color: #666;
}

.user-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.user-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  border-radius: 4px;
  background-color: #f5f5f5;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  margin-right: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #ccc;
  color: white;
  font-weight: bold;
}

.user-item.current-user {
  background-color: #e8f5e9;
}

.user-item.empty {
  background-color: #f5f5f5;
  color: #999;
  font-style: italic;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.user-name {
  font-weight: 500;
}

.host-badge {
  background-color: #4CAF50;
  color: white;
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.self-badge {
  background-color: #2196F3;
  color: white;
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.user-status {
  font-size: 0.8rem;
  color: #666;
}

.waiting-slot {
  width: 100%;
  text-align: center;
}

.user-count {
  margin-top: 1rem;
  text-align: center;
  font-size: 0.9rem;
  color: #666;
}
</style> 