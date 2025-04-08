<template>
  <div class="chat-container">
    <div class="chat-header">
      <h3 class="chat-title">聊天</h3>
    </div>
    
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="empty-messages">
        暂无消息，快来聊天吧
      </div>
      
      <template v-for="(message, index) in messages" :key="index">
        <!-- 系统消息 -->
        <div v-if="message.type === 'system' || message.is_system" class="system-message">
          <div class="system-content">{{ message.content }}</div>
          <div class="message-time">{{ formatTime(message.timestamp) }}</div>
        </div>
        
        <!-- 普通用户消息 -->
        <div v-else class="message-wrapper" :class="{ 'self-message': isSelfMessage(message) }">
          <!-- 左侧头像 (他人消息) -->
          <div v-if="!isSelfMessage(message)" class="avatar">
            <img :src="message.avatar || '/default_avatar.jpg'" alt="头像">
          </div>
          
          <div class="message-bubble-container">
            <!-- 用户名 -->
            <div class="message-sender">{{ message.username }}</div>
            
            <!-- 消息气泡 -->
            <div class="message-bubble">
              {{ message.content }}
            </div>
            
            <!-- 消息时间 -->
            <div class="message-time">{{ formatTime(message.timestamp) }}</div>
          </div>
          
          <!-- 右侧头像 (自己的消息) -->
          <div v-if="isSelfMessage(message)" class="avatar">
            <img :src="userStore.user?.avatar || '/default_avatar.jpg'" alt="头像">
          </div>
        </div>
      </template>
    </div>
    
    <div class="chat-input">
      <input 
        type="text" 
        v-model="newMessage" 
        @keyup.enter="sendMessage"
        placeholder="输入消息..." 
        :disabled="disabled"
      />
      <button @click="sendMessage" :disabled="!newMessage.trim() || disabled">发送</button>
    </div>
  </div>
</template>

<script>
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { userStore } from '../store/user'

export default {
  name: 'ChatComponent',
  
  props: {
    messages: {
      type: Array,
      default: () => []
    },
    roomId: {
      type: String,
      required: true
    },
    disabled: {
      type: Boolean,
      default: false
    }
  },
  
  emits: ['send-message'],
  
  setup(props, { emit }) {
    const newMessage = ref('')
    const messagesContainer = ref(null)
    
    // 当前用户ID
    const currentUserId = computed(() => userStore.user?.id || '')
    
    // 判断是否是自己发送的消息
    const isSelfMessage = (message) => {
      return message.user_id === currentUserId.value || 
             message.userId === currentUserId.value ||
             message.is_self === true
    }
    
    // 发送消息
    const sendMessage = () => {
      if (!newMessage.value.trim() || props.disabled) return
      
      const message = {
        userId: currentUserId.value,
        username: userStore.user?.username,
        content: newMessage.value.trim(),
        timestamp: Date.now(),
        roomId: props.roomId
      }
      
      emit('send-message', message)
      newMessage.value = ''
    }
    
    // 格式化时间
    const formatTime = (timestamp) => {
      if (!timestamp) return ''
      
      const date = new Date(timestamp)
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      
      return `${hours}:${minutes}`
    }
    
    // 当消息列表更新时，滚动到底部
    watch(() => props.messages.length, () => {
      scrollToBottom()
    })
    
    // 滚动到聊天框底部
    const scrollToBottom = async () => {
      await nextTick()
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    }
    
    // 组件挂载后滚动到底部
    onMounted(() => {
      scrollToBottom()
    })
    
    return {
      newMessage,
      messagesContainer,
      currentUserId,
      userStore,
      isSelfMessage,
      sendMessage,
      formatTime,
      scrollToBottom
    }
  }
}
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  height: 100%;
  justify-content: space-between;
}

.chat-header {
  padding: 0.75rem 1rem;
  background-color: #4CAF50;
  color: white;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  flex-shrink: 0;
}

.chat-title {
  margin: 0;
  font-size: 1.1rem;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 300px;
  max-height: calc(100% - 120px);
}

.empty-messages {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
  color: #999;
  font-style: italic;
}

/* 系统消息样式 */
.system-message {
  text-align: center;
  margin: 0.5rem 0;
}

.system-content {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background-color: rgba(0, 0, 0, 0.1);
  border-radius: 10px;
  font-size: 0.8rem;
  color: #666;
}

/* 消息包装容器 */
.message-wrapper {
  display: flex;
  margin-bottom: 0.5rem;
  align-items: flex-start;
}

/* 自己的消息靠右 */
.self-message {
  flex-direction: row-reverse;
}

/* 头像样式 */
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  margin: 0 0.5rem;
  flex-shrink: 0;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 消息气泡容器 */
.message-bubble-container {
  display: flex;
  flex-direction: column;
  max-width: 70%;
}

/* 用户名样式 */
.message-sender {
  font-size: 0.8rem;
  color: #555;
  margin-bottom: 0.25rem;
  padding: 0 0.25rem;
}

.self-message .message-sender {
  text-align: right;
}

/* 消息气泡 */
.message-bubble {
  padding: 0.75rem;
  border-radius: 12px;
  background-color: white;
  word-wrap: break-word;
  position: relative;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.self-message .message-bubble {
  background-color: #95ec69; /* 绿色气泡，类似微信 */
  color: #000;
}

/* 时间样式 */
.message-time {
  font-size: 0.7rem;
  color: #999;
  margin-top: 0.25rem;
  padding: 0 0.25rem;
}

.self-message .message-time {
  text-align: right;
}

.chat-input {
  display: flex;
  padding: 0.75rem;
  border-top: 1px solid #e6e6e6;
  background-color: white;
}

.chat-input input {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 20px;
  font-size: 1rem;
  margin-right: 0.5rem;
  background-color: #f5f5f5;
}

.chat-input button {
  padding: 0 1.25rem;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.chat-input button:hover:not(:disabled) {
  background-color: #45a049;
}

.chat-input button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

/* 滚动条样式 */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 6px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #999;
}
</style> 