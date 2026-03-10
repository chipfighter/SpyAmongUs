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
        :avatar="msg.avatarUrl || '/default_room_robot_avatar.jpg'"
      />
      
      <!-- 用户消息 -->
      <div v-else :class="['user-message', msg.user_id === currentUserId ? 'self-message' : '', msg.type === 'last_words' ? 'last-words-message' : '']">
        <!-- 其他用户消息 (左侧) -->
        <template v-if="msg.user_id !== currentUserId">
          <!-- 调试代码：添加检查消息类型的小标记 -->
          <span class="debug-type" v-if="false">{{msg.type}}</span>
          <div class="avatar" :class="{'eliminated-avatar': msg.type === 'last_words'}">
            <!-- 注意：getUserAvatar 需要父组件通过 prop 传入 user list 或直接传入 avatar url -->
            <img :src="getUserAvatarById(msg.user_id)" alt="用户头像" @error="onAvatarError">
          </div>
          <div class="message-content" :class="{'last-words-content': msg.type === 'last_words'}">
            <div class="username">{{ msg.username }} <span v-if="msg.type === 'last_words'" class="last-words-badge">遗言</span></div>
            <div class="text" v-if="msg.parsedContent" v-html="msg.parsedContent"></div>
            <div class="text" v-else>{{ msg.content }}</div>
            <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
          </div>
        </template>
        
        <!-- 自己的消息 (右侧) -->
        <template v-else>
          <div class="message-content self" :class="{'last-words-content': msg.type === 'last_words'}">
            <div class="username">{{ msg.username }} <span v-if="msg.type === 'last_words'" class="last-words-badge">遗言</span></div>
            <div class="text" v-if="msg.parsedContent" v-html="msg.parsedContent"></div>
            <div class="text" v-else>{{ msg.content }}</div>
            <div class="message-time">{{ formatTimestamp(msg.timestamp) }}</div>
          </div>
          <div class="avatar" :class="{'eliminated-avatar': msg.type === 'last_words'}">
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
  
  // 监听消息的isStreaming状态变化，特别是个别AI消息结束
  const newStoppedAiMessages = newMessages.filter(
    (msg, index) => 
      msg.type === 'ai_stream' && 
      !msg.isStreaming && 
      (index >= oldMessages.length || (oldMessages[index]?.isStreaming))
  );
  
  // 如果有AI消息结束并生成，强制执行一次更新
  if (newStoppedAiMessages.length > 0) {
    console.log('检测到AI消息结束并生成，强制执行一次更新');
    nextTick(() => {
      // 在下一行解决AI消息结束时的问题
    });
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

// 处理消息类型，确保遗言正确显示
watch(() => props.messages, (newMessages) => {
  // 处理每条消息，确保遗言类型被正确识别
  newMessages.forEach(msg => {
    if (msg.type === 'last_words' && !msg._processedForUI) {
      // 标记已处理，避免重复处理
      msg._processedForUI = true;
      console.log('处理遗言消息:', msg);
      
      // 添加额外的日志，帮助调试AI玩家遗言
      if (msg.user_id && msg.user_id.startsWith('llm_player_')) {
        console.log('检测到AI玩家遗言:', msg.user_id, msg.content);
      }
    }
  });
}, { deep: true, immediate: true });

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

/* 添加遗言相关样式 */
.last-words-message {
  /* 为遗言消息添加轻微的不同背景色 */
  background-color: rgba(245, 245, 245, 0.5);
  border-radius: 8px;
  padding: 5px;
  position: relative;
}

.last-words-message:before {
  content: '';
  position: absolute;
  top: -5px;
  left: 0;
  right: 0;
  height: 1px;
  background-color: rgba(204, 204, 204, 0.5);
}

.last-words-content {
  /* 为遗言内容添加特殊样式 */
}

.eliminated-avatar {
  position: relative;
}

.eliminated-avatar:after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  z-index: 1;
}

.eliminated-avatar img {
  /* 淘汰玩家的头像变灰 */
  filter: grayscale(100%);
  border: 2px solid #ff4d4f;
}

.last-words-badge {
  display: inline-block;
  font-size: 0.7rem;
  color: white;
  background-color: #cccccc;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 5px;
  vertical-align: middle;
}
</style> 