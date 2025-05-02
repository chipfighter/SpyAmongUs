<template>
  <div class="messages-container" ref="messagesContainer">
    <div v-for="(msg, index) in messages" :key="index" class="message-wrapper">
      <!-- 系统消息 -->
      <div v-if="msg.is_system" class="system-message">
        <div class="system-content">{{ msg.content }}</div>
        <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
      </div>
      
      <!-- AI流式消息 -->
      <AiStreamMessage
        v-else-if="msg.type === 'ai_stream'"
        :content="msg.content"
        :is-streaming="msg.isStreaming"
        :timestamp="msg.timestamp"
        :username="msg.username || 'AI助理'"
      />
      
      <!-- 用户消息 -->
      <div v-else :class="['user-message', msg.user_id === currentUserId ? 'self-message' : '']">
        <!-- 其他用户消息 (左侧) -->
        <template v-if="msg.user_id !== currentUserId">
          <div class="avatar">
            <!-- 注意：getUserAvatar 需要父组件通过 prop 传入 user list 或直接传入 avatar url -->
            <img :src="getUserAvatarById(msg.user_id)" alt="用户头像" @error="onAvatarError">
          </div>
          <div class="message-content">
            <div class="username">{{ msg.username }}</div>
            <div class="text" v-if="msg.parsedContent" v-html="msg.parsedContent"></div>
            <div class="text" v-else>{{ msg.content }}</div>
            <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
          </div>
        </template>
        
        <!-- 自己的消息 (右侧) -->
        <template v-else>
          <div class="message-content self">
            <div class="username">{{ msg.username }}</div>
            <div class="text" v-if="msg.parsedContent" v-html="msg.parsedContent"></div>
            <div class="text" v-else>{{ msg.content }}</div>
            <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
          </div>
          <div class="avatar">
             <!-- 需要当前用户的头像 -->
            <img :src="currentUserAvatar || '/default_avatar.jpg'" alt="我的头像" @error="onAvatarError">
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, ref, watch, nextTick, onMounted } from 'vue';
import AiStreamMessage from '@/components/Room/AiStreamMessage.vue'; // 导入移动后的组件

const props = defineProps({
  messages: {
    type: Array,
    required: true,
    default: () => []
  },
  currentUserId: {
    type: String,
    required: true,
    default: ''
  },
  // 新增：传入用户列表或映射以获取头像
  users: {
      type: Array,
      required: true,
      default: () => []
  },
  // 新增：传入当前用户头像
  currentUserAvatar: {
      type: [String, null],
      required: false,
      default: '/default_avatar.jpg'
  }
});

const messagesContainer = ref(null);

// --- 迁移的方法 --- 

const formatTimestamp = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  });
};

// 修改：根据传入的 users 列表查找头像
const getUserAvatarById = (userId) => {
  const user = props.users.find(u => u.id === userId);
  return user?.avatar_url || '/default_avatar.jpg';
};

// 处理 @ 提及的逻辑 (如果消息对象中没有预处理的 parsedContent，则需要在这里处理)
// 暂时假设父组件传递的 msg 对象已包含 parsedContent
/* 
const parseMentions = (content) => {
  const mentionRegex = /@\[([^:]+):([^\]]+)\]/g;
  return content.replace(mentionRegex, (match, userId, username) => {
    const isAi = userId === 'ai_assistant';
    const mentionClass = isAi ? 'mention ai-mention' : 'mention user-mention';
    return `<span class="${mentionClass}" data-user-id="${userId}">@${username}</span>`;
  });
};
*/

// 处理头像加载失败
const onAvatarError = (event) => {
  event.target.src = '/default_avatar.jpg';
};

// --- 自动滚动逻辑 --- 
// 监听消息数组的变化，滚动到底部
watch(() => props.messages, (newMessages, oldMessages) => {
  if (newMessages.length !== oldMessages.length) {
      scrollToBottom();
  }
}, { deep: true });

// 组件挂载后也滚动一次
onMounted(() => {
    scrollToBottom();
});

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
};

</script>

<style scoped>
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 10px; /* 保持滚动条边距 */
  margin-bottom: 15px; /* 保持与输入框间距 */
}

.message-wrapper {
  margin-bottom: 15px;
}

.system-message {
  text-align: center;
  margin: 10px 0;
}

.system-content {
  display: inline-block;
  padding: 6px 12px;
  background-color: rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  color: #666;
  font-size: 13px;
}

.message-time {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.user-message {
  display: flex;
  margin: 10px 0;
  align-items: flex-start;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  margin: 0 10px;
  flex-shrink: 0;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
}

.message-content.self {
  align-items: flex-end;
}

.username {
  font-size: 12px;
  color: #666;
  margin-bottom: 2px;
}

.text {
  padding: 8px 12px;
  border-radius: 10px;
  background-color: #E3F2FD; /* 他人消息 */
  word-break: break-all;
  /* 如果需要处理 pre-wrap 或 pre-line，可以在这里添加 white-space 属性 */
}

.self-message {
  flex-direction: row-reverse;
}

.self-message .text {
  background-color: #3b71ca; /* 自己消息 */
  color: white;
}

/* AI 消息气泡颜色 (复用 RoomView 的样式) */
/* AI流式组件内部可能自带样式，这里是备用 */
/* .ai-message-bubble .text { ... } */
.ai-stream-message .text { /* 假设 AiStreamMessage 组件内部的文本容器是 .text */
  background-color: #F5F5F5; 
  color: #333;
}

/* @提及 样式 (如果 parseMentions 在此组件处理) */
/* 
.mention { ... }
.user-mention { ... }
.ai-mention { ... } 
*/
</style> 