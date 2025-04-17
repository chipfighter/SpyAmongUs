<template>
  <div v-if="show" class="secret-chat-modal-overlay" @click.self="emitClose"> 
    <div class="secret-chat-modal">
      <div class="secret-chat-content">
        <div class="secret-chat-header">
          <h3>秘密聊天</h3>
          <button class="close-button" @click="emitClose">×</button>
        </div>
        
        <div class="secret-messages-container" ref="secretMessagesContainerRef">
          <div v-for="(msg, index) in messages" :key="index" class="message-wrapper">
            <div :class="['user-message', msg.user_id === currentUser.id ? 'self-message' : '']">
              <!-- 其他用户消息 (左侧) -->
              <template v-if="msg.user_id !== currentUser.id">
                <div class="avatar">
                  <img :src="getUserAvatarInternal(msg.user_id)" alt="用户头像">
                </div>
                <div class="message-content">
                  <div class="username">{{ msg.username }}</div>
                  <div class="text">{{ msg.content }}</div>
                  <div class="message-time">{{ formatTimestampInternal(msg.timestamp) }}</div>
                </div>
              </template>
              
              <!-- 自己的消息 (右侧) -->
              <template v-else>
                <div class="message-content self">
                  <div class="username">{{ msg.username }}</div>
                  <div class="text">{{ msg.content }}</div>
                  <div class="message-time">{{ formatTimestampInternal(msg.timestamp) }}</div>
                </div>
                <div class="avatar">
                  <img :src="currentUser.avatar_url || '/default_avatar.jpg'" alt="我的头像">
                </div>
              </template>
            </div>
          </div>
        </div>
        
        <!-- 选择目标用户 -->
        <div class="secret-targets">
          <div>发送给:</div>
          <div class="target-users">
            <div 
              v-for="user in targets" 
              :key="user.id"
              class="target-user"
              :class="{ selected: selectedTargets.includes(user.id) }"
              @click="emitToggleTarget(user.id)"
            >
              {{ user.username || user.username }}
            </div>
          </div>
        </div>
        
        <!-- 输入框 -->
        <div class="input-container">
          <input 
            type="text" 
            :value="newMessage" 
            @input="emitUpdateNewMessage($event.target.value)"
            @keyup.enter="emitSendMessage"
            placeholder="输入秘密消息..." 
            :disabled="!isConnected || selectedTargets.length === 0"
            ref="secretInputRef"
          />
          <button 
            @click="emitSendMessage" 
            :disabled="!isConnected || selectedTargets.length === 0 || !newMessage.trim()"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue';

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
    default: false
  },
  messages: {
    type: Array,
    required: true,
    default: () => []
  },
  currentUser: {
    type: Object,
    required: true,
    default: () => ({ id: '', username: '', avatar_url: '' })
  },
  targets: { // Secret chat targets
    type: Array,
    required: true,
    default: () => []
  },
  selectedTargets: {
    type: Array,
    required: true,
    default: () => []
  },
  newMessage: { // v-model:newMessage
    type: String,
    required: true,
    default: ''
  },
  isConnected: {
    type: Boolean,
    required: true,
    default: false
  },
  roomUsers: { // Needed for getUserAvatarInternal
      type: Array,
      required: true,
      default: () => []
  }
});

const secretMessagesContainerRef = ref(null);
const secretInputRef = ref(null);

// --- Helper Functions (Migrated) ---
const formatTimestampInternal = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  });
};

const getUserAvatarInternal = (userId) => {
  const user = props.roomUsers.find(u => u.id === userId);
  return user?.avatar_url || '/default_avatar.jpg';
};

// --- Emit Wrappers ---
const emitClose = () => {
  emit('close');
};

const emitUpdateNewMessage = (value) => {
  emit('update:newMessage', value);
};

const emitSendMessage = () => {
  if (props.newMessage.trim() && props.selectedTargets.length > 0 && props.isConnected) {
    emit('send-message');
  }
};

const emitToggleTarget = (userId) => {
  emit('toggle-target', userId);
};

// --- Scroll to bottom when messages change ---
watch(() => props.messages, () => {
  nextTick(() => {
    const container = secretMessagesContainerRef.value;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  });
}, { deep: true });

// --- Focus input when modal opens ---
watch(() => props.show, (newVal) => {
    if (newVal) {
        nextTick(() => {
            if (secretInputRef.value) {
                secretInputRef.value.focus();
            }
        });
    }
});

</script>

<style scoped>
.secret-chat-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1001; /* Higher than other elements */
}

.secret-chat-modal {
  /* Removed overlay styles, now handled by the wrapper */
}

.secret-chat-content {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  width: 500px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.secret-chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
  margin-bottom: 15px;
}

.secret-chat-header h3 {
  margin: 0;
  font-size: 1.2rem;
}

.close-button {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #aaa;
}

.close-button:hover {
    color: #333;
}

.secret-messages-container {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 15px;
  padding-right: 5px; /* Add some padding for scrollbar */
}

/* Message styles from RoomView */
.message-wrapper {
  margin-bottom: 15px;
}

.user-message {
  display: flex;
  align-items: flex-start;
}

.user-message.self-message {
  justify-content: flex-end;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 10px;
  flex-shrink: 0;
}

.self-message .avatar {
  margin-right: 0;
  margin-left: 10px;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.message-content {
  max-width: 70%;
}

.message-content.self {
  text-align: right;
}

.username {
  font-size: 0.8rem;
  color: #888;
  margin-bottom: 2px;
}

.message-content.self .username {
    /* No change needed, alignment handled by flex */
}

.text {
  background-color: #f0f0f0;
  padding: 8px 12px;
  border-radius: 10px;
  word-wrap: break-word;
  white-space: pre-wrap;
  font-size: 0.95rem;
}

.self-message .text {
  background-color: #1890ff;
  color: white;
  border-top-right-radius: 0;
}

.user-message:not(.self-message) .text {
    border-top-left-radius: 0;
}

.message-time {
  font-size: 0.75rem;
  color: #aaa;
  margin-top: 3px;
}

.self-message .message-time {
  text-align: right;
}


/* Target Selection */
.secret-targets {
  border-top: 1px solid #eee;
  padding-top: 15px;
  margin-bottom: 15px;
}

.secret-targets > div:first-child {
  font-weight: bold;
  margin-bottom: 8px;
}

.target-users {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.target-user {
  padding: 5px 10px;
  border: 1px solid #ccc;
  border-radius: 15px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.target-user.selected {
  background-color: #1890ff;
  color: white;
  border-color: #1890ff;
}

.target-user:not(.selected):hover {
  background-color: #f0f0f0;
}

/* Input Area */
.input-container {
  display: flex;
  align-items: center;
  border-top: 1px solid #eee;
  padding-top: 15px;
}

.input-container input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  outline: none;
  margin-right: 10px;
}

.input-container input:focus {
  border-color: #1890ff;
}

.input-container button {
  padding: 10px 15px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.input-container button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

</style> 