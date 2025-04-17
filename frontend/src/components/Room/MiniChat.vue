<template>
  <div v-if="show" class="mini-chat">
    <div class="mini-chat-header">
      <button class="back-button" @click="emitClose">👈 返回房间</button>
      <h3>{{ roomName }}</h3>
    </div>
    <div class="mini-chat-messages" ref="miniMessagesContainerRef">
      <!-- Only display last N messages passed via prop -->
      <div v-for="(msg, index) in messages" :key="msg.id || index" class="mini-message">
        <div v-if="msg.is_system" class="mini-system-message">
          {{ msg.content }}
        </div>
        <div v-else class="mini-user-message">
          <span class="mini-username">{{ msg.username }}:</span>
          <span class="mini-content" v-html="parseMiniMessageContent(msg.content)"></span>
        </div>
      </div>
    </div>
    <div class="mini-chat-input">
      <input 
        type="text" 
        :value="newMessage" 
        @input="emitUpdateNewMessage($event.target.value)"
        @keyup.enter="emitSendMessage"
        placeholder="输入消息..." 
        :disabled="!isConnected"
        ref="miniInputRef"
      />
      <button @click="emitSendMessage" :disabled="!isConnected || !newMessageTrimmed">
        发送
      </button>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, ref, watch, nextTick, computed } from 'vue';

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
    default: false
  },
  roomName: {
    type: String,
    required: true,
    default: ''
  },
  messages: { // Expecting already sliced messages (e.g., last 10)
    type: Array,
    required: true,
    default: () => []
  },
  newMessage: { // For v-model
    type: String,
    required: true,
    default: ''
  },
  isConnected: {
    type: Boolean,
    required: true,
    default: false
  }
});

const emit = defineEmits([
  'close',
  'update:newMessage',
  'send-message'
]);

const miniMessagesContainerRef = ref(null);
const miniInputRef = ref(null);

const newMessageTrimmed = computed(() => props.newMessage.trim());

const emitClose = () => {
  emit('close');
};

const emitUpdateNewMessage = (value) => {
  emit('update:newMessage', value);
};

const emitSendMessage = () => {
  if (newMessageTrimmed.value && props.isConnected) {
    emit('send-message');
  }
};

// Basic content parsing (e.g., escaping HTML, can be extended)
const parseMiniMessageContent = (content) => {
    if (!content) return '';
    // Basic HTML escaping to prevent XSS in v-html
    const tempDiv = document.createElement('div');
    tempDiv.textContent = content;
    return tempDiv.innerHTML;
    // Can add link detection or simple markdown later if needed
};

// Scroll to bottom when messages change or component becomes visible
watch([() => props.messages, () => props.show], () => {
  if (props.show) {
      nextTick(() => {
        const container = miniMessagesContainerRef.value;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
  }
}, { deep: true, immediate: true }); // Immediate might be needed if shown initially

// Focus input when modal becomes visible
watch(() => props.show, (newVal) => {
  if (newVal) {
    nextTick(() => {
      if (miniInputRef.value) {
        miniInputRef.value.focus();
      }
    });
  }
});

</script>

<style scoped>
.mini-chat {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 300px;
  height: 400px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  z-index: 1000;
  transition: opacity 0.3s, transform 0.3s; /* Add transition */
  opacity: 1;
  transform: translateY(0);
}

/* Hide animation (if needed, though v-if handles removal) */
/*.mini-chat:not(.v-if-true) { 
  opacity: 0;
  transform: translateY(20px);
}*/

.mini-chat-header {
  display: flex;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0; /* Prevent header from shrinking */
}

.mini-chat-header h3 {
  margin: 0;
  font-size: 14px;
  flex: 1;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.back-button {
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  color: #1890ff;
  padding: 0 8px 0 0; /* Add padding */
  white-space: nowrap;
}

.mini-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.mini-message {
  margin-bottom: 8px;
  font-size: 13px;
}

.mini-system-message {
  text-align: center;
  color: #999;
  padding: 2px 0;
  font-style: italic;
}

.mini-user-message {
  word-break: break-word;
}

.mini-username {
  font-weight: bold;
  margin-right: 5px;
  color: #555;
}

.mini-content {
    color: #333;
}

.mini-chat-input {
  display: flex;
  padding: 10px;
  border-top: 1px solid #f0f0f0;
  flex-shrink: 0; /* Prevent input from shrinking */
}

.mini-chat-input input {
  flex: 1;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 8px;
  outline: none;
  font-size: 13px;
  min-width: 0; /* Allow input to shrink if needed */
}

.mini-chat-input input:focus {
    border-color: #1890ff;
}

.mini-chat-input button {
  margin-left: 8px;
  padding: 8px 12px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.mini-chat-input button:hover:not(:disabled) {
    background-color: #40a9ff;
}

.mini-chat-input button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
</style> 