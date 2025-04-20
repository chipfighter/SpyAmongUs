<template>
  <div class="input-container" @click="focusInput">
    <div class="input-wrapper">
      <textarea 
        :value="modelValue" 
        @input="handleInput"
        @keydown.enter="handleEnterKey"
        @keydown="handleMentionNavigation"
        placeholder="输入消息..." 
        :disabled="!isConnected"
        ref="messageInputRef"
        class="message-textarea"
        rows="1"
      ></textarea>
      
      <!-- @用户列表弹出框 -->
      <div v-if="showMentionPopup" class="mention-popup">
        <!-- AI助手 -->
        <div 
          v-if="showAiAssistant" 
          :class="['mention-item', { 'active': selectedMentionIndex === 0 }]"
          @click="selectMention({ id: 'ai_assistant', username: 'AI助理' })"
        >
          <div class="mention-avatar">
            <img src="/default_room_robot_avatar.jpg" alt="AI助理">
          </div>
          <div class="mention-name">AI助理</div>
        </div>
        
        <!-- 分隔线 -->
        <div v-if="showAiAssistant && filteredMentionUsers.length > 0" class="mention-divider"></div>
        
        <!-- 用户列表 -->
        <div 
          v-for="(user, index) in filteredMentionUsers" 
          :key="user.id"
          :class="['mention-item', { 'active': showAiAssistant ? index + 1 === selectedMentionIndex : index === selectedMentionIndex }]"
          @click="selectMention(user)"
        >
          <div class="mention-avatar">
            <img :src="user.avatar_url || '/default_avatar.jpg'" alt="用户头像" @error="onAvatarError">
          </div>
          <div class="mention-name">{{ user.username || user.username }}</div>
        </div>
      </div>
    </div>
    <button @click="emitSendMessage" :disabled="!isConnected || !modelValue.trim()">
      发送
    </button>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits, computed, nextTick } from 'vue';

const props = defineProps({
  modelValue: { // for v-model
    type: String,
    required: true,
    default: ''
  },
  isConnected: {
    type: Boolean,
    required: true,
    default: false
  },
  users: { // for mentions
    type: Array,
    required: true,
    default: () => []
  },
  currentUserId: { // for mentions (filtering self)
    type: String,
    required: true,
    default: ''
  }
});

const emit = defineEmits([
    'update:modelValue', // for v-model
    'send-message'
]);

const messageInputRef = ref(null);

// --- @ Mention Logic --- 
const showMentionPopup = ref(false);
const mentionQuery = ref('');
const mentionStartIndex = ref(-1);
const filteredMentionUsers = ref([]);
const selectedMentionIndex = ref(0);
const showAiAssistant = ref(true); // 控制AI助手是否显示

const handleInput = (event) => {
  const text = event.target.value;
  emit('update:modelValue', text); // Update v-model in parent
  
  const lastAtSignIndex = text.lastIndexOf('@');
  
  // Auto-resize textarea
  adjustTextareaHeight();

  if (lastAtSignIndex !== -1) {
    const textAfterAt = text.substring(lastAtSignIndex + 1);
    const hasCloseBracket = text.substring(lastAtSignIndex).includes(']');
    const charBeforeAt = text[lastAtSignIndex - 1];

    // Trigger mention popup if conditions met
    if (!textAfterAt.includes(' ') && !hasCloseBracket && (charBeforeAt === undefined || charBeforeAt === ' ' || charBeforeAt === '\n')) {
        mentionStartIndex.value = lastAtSignIndex;
        mentionQuery.value = textAfterAt.trim();
        showMentionPopup.value = true;
        filterMentionUsers();
        selectedMentionIndex.value = 0; // Default to AI assistant if shown
        return;
    }
  }
  
  showMentionPopup.value = false; // Close popup otherwise
};

const adjustTextareaHeight = () => {
  nextTick(() => { // Ensure DOM is updated before calculating scrollHeight
    const textarea = messageInputRef.value;
    if (textarea) {
      textarea.style.height = 'auto'; // Reset height to calculate natural height
      textarea.style.height = Math.min(150, textarea.scrollHeight) + 'px'; // Set new height, capped at 150px
    }
  });
};

const filterMentionUsers = () => {
  const query = mentionQuery.value.toLowerCase();
  filteredMentionUsers.value = props.users.filter(user => 
    user.id !== props.currentUserId && 
    user.username &&
    user.username.toLowerCase().includes(query)
  );
  showAiAssistant.value = 'ai助理'.includes(query) || 'ai'.includes(query) || query === '';
};

const handleMentionNavigation = (event) => {
  if (!showMentionPopup.value) return;

  const totalOptions = filteredMentionUsers.value.length + (showAiAssistant.value ? 1 : 0);
  if (totalOptions === 0) return;

  if (event.key === 'Escape') {
    event.preventDefault();
    showMentionPopup.value = false;
  } else if (event.key === 'Tab' || event.key === 'Enter') { // Allow Enter here as well
     if (showMentionPopup.value) { // Check again in case ESC was just pressed
        event.preventDefault();
        selectCurrentMention();
     }
  }
};

const selectCurrentMention = () => {
    if (showAiAssistant.value && selectedMentionIndex.value === 0) {
      selectMention({ id: 'ai_assistant', username: 'AI助理' });
    } else {
      const userIndex = showAiAssistant.value ? selectedMentionIndex.value - 1 : selectedMentionIndex.value;
      if (userIndex >= 0 && userIndex < filteredMentionUsers.value.length) {
        selectMention(filteredMentionUsers.value[userIndex]);
      }
    }
};

const selectMention = (user) => {
  const beforeMention = props.modelValue.substring(0, mentionStartIndex.value);
  const afterMention = props.modelValue.substring(mentionStartIndex.value + mentionQuery.value.length + 1);
  const newText = `${beforeMention}@[${user.id}:${user.username || user.username}] ${afterMention}`;
  emit('update:modelValue', newText);
  showMentionPopup.value = false;
  focusInput(); // Focus after selection
  nextTick(adjustTextareaHeight); // Adjust height after text change
};

// Handle Enter key specifically for sending message OR selecting mention
const handleEnterKey = (event) => {
  if (showMentionPopup.value) {
      // Already handled by handleMentionNavigation
      // event.preventDefault(); // Prevent default newline/send
      // selectCurrentMention(); 
  } else {
    if (!event.shiftKey) { // Send on Enter (not Shift+Enter)
      event.preventDefault(); 
      emitSendMessage();
    }
    // Allow default behavior (newline) for Shift+Enter
  }
};

const emitSendMessage = () => {
  if (props.modelValue.trim() && props.isConnected) {
      emit('send-message'); // Emit event, parent handles actual sending
  }
};

const focusInput = () => {
  nextTick(() => {
      if (messageInputRef.value && props.isConnected) {
          messageInputRef.value.focus();
      }
  });
};

// Headless UI or other libraries might be better for complex popups

// Handle avatar error within mention popup
const onAvatarError = (event) => {
  event.target.src = '/default_avatar.jpg';
};

</script>

<style scoped>
.input-container {
  display: flex;
  margin-top: auto; /* Pushes input to bottom */
  background-color: #fff;
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  cursor: text;
  align-items: flex-end; /* Align items to bottom for textarea */
}

.input-wrapper {
  position: relative; /* Needed for mention popup positioning */
  flex: 1;
  display: flex; /* Ensure textarea takes full width */
}

.message-textarea {
  flex: 1;
  border: none;
  padding: 10px 15px;
  border-radius: 4px;
  outline: none;
  font-size: 1rem;
  resize: none !important; /* Ensure resize handle is hidden */
  overflow-y: auto; /* Allow vertical scroll if needed */
  min-height: 40px; /* ~1 line height + padding */
  max-height: 150px; /* Limit height expansion */
  width: 100%; /* Take full width of wrapper */
  white-space: pre-wrap; /* Handle line breaks */
  word-break: break-all;
  line-height: 1.4;
  box-sizing: border-box; /* Include padding in height calculation */
}

.input-container button {
  margin-left: 10px;
  padding: 10px 20px;
  min-width: 80px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  align-self: flex-end; /* Align button to bottom */
  height: 40px; /* Match default textarea height */
}

.input-container button:hover {
  background-color: #40a9ff;
}

.input-container button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

/* Mention Popup Styles */
.mention-popup {
  position: absolute;
  bottom: calc(100% + 5px); /* Position above the input */
  left: 0;
  width: 200px;
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
  border: 1px solid #eee;
}

.mention-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
}

.mention-item:hover:not(.active) {
  background-color: #f5f5f5;
}

.mention-item.active {
  background-color: #e6f7ff;
  /* border-left: 3px solid #1890ff; */ /* Optional active indicator */
}

.mention-divider {
  height: 1px;
  background-color: #e8e8e8;
  margin: 4px 0;
}

.mention-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 8px;
  flex-shrink: 0;
}

.mention-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mention-name {
  font-size: 0.85rem;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style> 