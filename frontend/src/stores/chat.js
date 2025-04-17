import { defineStore } from 'pinia'

// 简单的消息列表长度限制
const MAX_MESSAGES = 200;

export const useChatStore = defineStore('chat', {
  state: () => ({
    // 公共聊天消息列表
    messages: [],
    // 秘密聊天消息列表
    secretMessages: [],
    // AI 流式消息相关状态 (如果需要集中管理)
    // currentAiStreamSession: null,
    // isStreaming: false,
  }),
  actions: {
    // 添加收到的公共消息 (由 websocketStore 调用)
    addMessage(message) {
      console.log('[ChatStore] Adding message:', message);
      // TODO: More sophisticated handling for different types (system, chat, ai_stream) needed?
      // For now, just push everything into the main list.
      this.messages.push(message);
      // Keep the list length manageable
      if (this.messages.length > MAX_MESSAGES) {
        this.messages.shift(); // Remove the oldest message
      }
    },
    // 添加收到的秘密消息 (由 websocketStore 调用)
    addSecretMessage(message) {
      console.log('[ChatStore] Adding secret message:', message);
      this.secretMessages.push(message);
      // Keep the list length manageable
      if (this.secretMessages.length > MAX_MESSAGES) {
        this.secretMessages.shift(); // Remove the oldest message
      }
    },
    // 加载缓存的消息 (例如从 localStorage)
    loadCachedMessages(cachedMessages, cachedSecretMessages) {
      console.log(`[ChatStore] Loading cached messages: ${cachedMessages?.length || 0} public, ${cachedSecretMessages?.length || 0} secret`);
      this.messages = Array.isArray(cachedMessages) ? cachedMessages : [];
      this.secretMessages = Array.isArray(cachedSecretMessages) ? cachedSecretMessages : [];
    },
    // 清空消息
    clearMessages() {
      console.log('[ChatStore] Clearing all messages');
      this.messages = [];
      this.secretMessages = [];
    },
  },
  getters: {
      // 获取用于迷你聊天的最后 N 条消息
      miniChatMessages: (state) => state.messages.slice(-10),
  }
}) 