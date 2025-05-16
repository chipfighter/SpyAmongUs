import { defineStore } from 'pinia'
import { nextTick } from 'vue'

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
      
      // 简化处理逻辑：所有消息都直接添加到末尾
      this.messages.push(message);
      
      // 使用nextTick确保视图更新
      nextTick(() => {
        // 空函数，只是触发视图更新周期
      });
      
      // Keep the list length manageable
      if (this.messages.length > MAX_MESSAGES) {
        this.messages.shift(); // Remove the oldest message
      }
    },
    
    // 更新AI流式消息
    updateAiStreamMessage(sessionId, updates) {
      // 查找消息索引
      const messageIndex = this.messages.findIndex(msg => 
        msg.id === sessionId && msg.type === 'ai_stream'
      );
      
      if (messageIndex !== -1) {
        // 使用原对象的所有属性加上新的更新来创建新对象
        const updatedMessage = {
          ...this.messages[messageIndex],
          ...updates,
          // 更新timestamp确保Vue检测到变化
          _updateTimestamp: Date.now()
        };
        
        // 替换原消息对象
        this.messages.splice(messageIndex, 1, updatedMessage);
        console.log(`[ChatStore] 更新AI流式消息 ${sessionId}, 更新内容:`, updates);
        
        // 确保Vue更新视图
        nextTick(() => {
          // 什么都不做，只为触发视图更新
        });
      } else {
        console.warn(`[ChatStore] 无法找到AI流式消息 ${sessionId} 进行更新`);
      }
    },
    
    // 添加收到的秘密消息 (由 websocketStore 调用)
    addSecretMessage(message) {
      console.log('[ChatStore] Adding secret message:', message);
      this.secretMessages.push(message);
      
      // 使用nextTick确保视图更新
      nextTick(() => {
        // 空函数，只是触发视图更新周期
      });
      
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