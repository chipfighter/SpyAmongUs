<template>
  <div class="user-list-container">
    <h2 class="user-list-title">{{ userCount }}/{{ roomData?.maxUsers || 8 }} 玩家</h2>
    
    <!-- 调试信息区域 -->
    <div v-if="debugMode" class="debug-panel">
      <div class="debug-title">调试信息</div>
      <div>用户列表长度: {{ users.length }}</div>
      <div>当前用户ID: {{ currentUserId }}</div>
      <div>房主ID: {{ roomData?.hostId }}</div>
      <div>房间ID: {{ roomData?.id }}</div>
      <div>WebSocket连接: {{ isConnected ? '已连接' : '未连接' }}</div>
      <div v-if="users.length > 0">
        第一位用户: {{ users[0]?.username }} ({{ users[0]?.id }})
      </div>
    </div>
    
    <!-- 用户列表为空的提示 -->
    <div v-if="userListIsEmpty" class="empty-list-warning">
      <p><strong>玩家列表为空!</strong></p>
      <p>可能原因:</p>
      <ul>
        <li>WebSocket连接未成功建立</li>
        <li>房间创建/加入过程未完成</li>
        <li>服务器未返回用户数据</li>
      </ul>
      <p>请检查浏览器控制台获取更多信息</p>
    </div>
    
    <!-- 实际用户列表 -->
    <div v-else class="user-list">
      <div v-for="user in users" :key="user.id" class="user-item" :class="getUserClass(user)">
        <div class="user-avatar" :style="getAvatarStyle(user)"></div>
        <div class="user-info">
          <div class="user-name">{{ user.username }}{{ user.isHost || user.is_host ? ' (房主)' : '' }}</div>
          <div class="user-status">{{ user.status }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import websocketService from '../services/websocket';

const props = defineProps({
  users: {
    type: Array,
    default: () => []
  },
  currentUser: {
    type: Object,
    default: () => ({})
  },
  roomData: {
    type: Object,
    default: () => null
  }
});

// 调试模式
const debugMode = ref(true);

// 获取当前用户ID
const currentUserId = computed(() => {
  // 优先使用props传入的currentUser
  if (props.currentUser && props.currentUser.id) {
    return props.currentUser.id;
  }
  
  // 否则从localStorage获取
  try {
    return JSON.parse(localStorage.getItem('user'))?.id || '';
  } catch (e) {
    console.error('获取当前用户ID失败:', e);
    return '';
  }
});

// 用户数量计算属性
const userCount = computed(() => {
  return props.users ? props.users.length : 0;
});

// 判断WebSocket是否连接
const isConnected = computed(() => {
  return websocketService.isConnected;
});

// 用户列表是否为空
const userListIsEmpty = computed(() => {
  return !props.users || props.users.length === 0;
});

// 获取用户CSS类
const getUserClass = (user) => {
  const classes = [];
  
  // 处理用户名可能带有空格的情况
  const userId = user.id || '';
  const currentId = currentUserId.value || '';
  
  if (userId.trim() === currentId.trim()) {
    classes.push('current-user');
  }
  
  if (user.isHost || user.is_host) {
    classes.push('host');
  }
  
  if (user.status === 'ready' || user.status === '准备') {
    classes.push('ready');
  }
  
  return classes;
};

// 获取头像样式
const getAvatarStyle = (user) => {
  // 检查用户是否有头像
  if (user.avatar) {
    // 检查是否是完整URL或相对路径
    if (user.avatar.startsWith('http') || user.avatar.startsWith('/')) {
      return { backgroundImage: `url(${user.avatar})` };
    }
    
    // 否则可能是相对路径
    return { backgroundImage: `url(/${user.avatar})` };
  }
  
  // 如果没有头像，使用背景色头像
  const userIdSum = [...(user.id || '0')].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const hue = userIdSum % 360;
  return {
    backgroundColor: `hsl(${hue}, 70%, 50%)`,
    color: 'white',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    fontSize: '1.2em',
    fontWeight: 'bold'
  };
};

// 在组件挂载时记录用户数据
onMounted(() => {
  console.log('[UserList] 组件挂载，用户列表:', props.users);
  console.log('[UserList] 当前用户:', props.currentUser);
  console.log('[UserList] 房间数据:', props.roomData);
});

// 监听用户列表变化
watch(() => props.users, (newUsers) => {
  console.log('[UserList] 用户列表已更新:', newUsers);
}, { deep: true });

</script>

<style scoped>
.user-list-container {
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 20px;
}

.user-list-title {
  font-size: 1.2rem;
  margin-bottom: 15px;
  color: #495057;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 8px;
}

.user-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.user-item {
  display: flex;
  align-items: center;
  padding: 10px;
  background-color: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  transition: transform 0.2s, box-shadow 0.2s;
}

.user-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 3px 6px rgba(0,0,0,0.12);
}

.user-item.current-user {
  border-left: 3px solid #4c6ef5;
}

.user-item.host {
  border-left: 3px solid #fd7e14;
}

.user-item.ready {
  background-color: #e6f7ec;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  margin-right: 12px;
  background-size: cover;
  background-position: center;
  background-color: #e9ecef;
}

.user-info {
  flex: 1;
}

.user-name {
  font-weight: 600;
  margin-bottom: 2px;
  color: #212529;
}

.user-status {
  font-size: 0.85rem;
  color: #6c757d;
}

.debug-panel {
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f1f3f5;
  border: 1px dashed #adb5bd;
  border-radius: 4px;
  font-size: 0.85rem;
}

.debug-title {
  font-weight: bold;
  margin-bottom: 5px;
  color: #495057;
}

.empty-list-warning {
  padding: 15px;
  background-color: #fff3cd;
  border: 1px solid #ffeeba;
  border-radius: 6px;
  color: #856404;
  margin: 10px 0;
}

.empty-list-warning ul {
  margin-top: 5px;
  margin-bottom: 5px;
  padding-left: 20px;
}
</style> 