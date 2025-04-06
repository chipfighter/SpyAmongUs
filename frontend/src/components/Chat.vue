<template>
  <div class="chat-container">
    <div class="chat-header">
      <h3 class="chat-title">聊天</h3>
    </div>
    
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="empty-messages">
        暂无消息，快来聊天吧
      </div>
      
      <div v-for="(message, index) in messages" :key="index" class="message" :class="{ 'self-message': message.userId === currentUserId }">
        <div class="message-sender">{{ message.username || '系统' }}</div>
        <div class="message-content">{{ message.content }}</div>
        <div class="message-time">{{ formatTime(message.timestamp) }}</div>
      </div>
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
  background-color: white;
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
  gap: 0.75rem;
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

.message {
  max-width: 80%;
  padding: 0.75rem;
  border-radius: 8px;
  background-color: #f1f1f1;
  align-self: flex-start;
}

.self-message {
  background-color: #e8f5e9;
  align-self: flex-end;
}

.message-sender {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
  color: #444;
}

.message-content {
  word-break: break-word;
}

.message-time {
  font-size: 0.75rem;
  color: #888;
  margin-top: 0.25rem;
  text-align: right;
}

.chat-input {
  display: flex;
  padding: 0.75rem;
  border-top: 1px solid #eee;
}

.chat-input input {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  margin-right: 0.5rem;
}

.chat-input button {
  padding: 0 1.25rem;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
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