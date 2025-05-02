<!-- AI流式消息组件 -->
<template>
  <div class="ai-stream-message">
    <!-- AI头像和名称 -->
    <div class="avatar">
      <img src="/default_room_robot_avatar.jpg" :alt="username">
    </div>
    <div class="message-content">
      <div class="username">{{ username }}</div>
      <div class="text">
        <!-- 当内容为空且正在streaming时显示加载动画 -->
        <div v-if="isStreaming && !processedContent" class="loading-dots">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <!-- 否则显示内容 -->
        <span v-else v-html="formattedContent"></span>
        <!-- 只在流式输出进行中显示打字光标，消息结束后不显示 -->
        <span v-if="isStreaming && processedContent.length > 0" class="cursor"></span>
      </div>
      <div class="message-time">{{ formatTime }}</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AiStreamMessage',
  props: {
    content: {
      type: String,
      default: ''
    },
    isStreaming: {
      type: Boolean,
      default: false
    },
    timestamp: {
      type: Number,
      default: () => Date.now()
    },
    username: {
      type: String,
      default: 'AI助理'
    }
  },
  data() {
    return {
      // 最近一次接收内容的末尾字符，用于检测跨块换行（主要是解决llm临时缓冲的问题）
      lastEndChars: '',
      // 最终处理后的内容
      processedContent: ''
    }
  },
  computed: {
    formatTime() {
      const date = new Date(this.timestamp);
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      });
    },
    formattedContent() {
      // 处理换行和空格
      if (!this.processedContent) return '';
      
      // 确保最终输出时也进行多余空行过滤
      return this.processedContent
        .replace(/\n{3,}/g, '\n\n') // 额外保险：将3个及以上连续换行符替换为2个
        .replace(/\n/g, '<br>')
        .replace(/ /g, '&nbsp;');
    }
  },
  watch: {
    content: {
      immediate: true,
      handler(newContent, oldContent) {
        if (!newContent) {
          this.processedContent = '';
          this.lastEndChars = '';
          return;
        }
        
        // 首次接收内容
        if (!oldContent) {
          // 预处理初始内容，移除多余空行
          this.processedContent = newContent.replace(/\n{3,}/g, '\n\n');
          // 保存结尾字符
          this.lastEndChars = this.processedContent.slice(-3);
          return;
        }
        
        // 获取新增内容
        const newChunk = newContent.slice(oldContent.length);
        
        // 检查跨块换行：将上次内容末尾与新内容开头拼接检查
        const checkStr = this.lastEndChars + newChunk;
        const hasExcessiveNewlines = checkStr.match(/\n{3,}/);
        
        // 处理跨块多余换行
        if (hasExcessiveNewlines) {
          // 将跨块多行换行符替换为两个
          const fixed = checkStr.replace(/\n{3,}/g, '\n\n');
          // 更新处理后内容
          this.processedContent = this.processedContent.slice(0, -this.lastEndChars.length) + fixed;
        } else {
          // 无需特殊处理，直接追加新内容
          this.processedContent += newChunk;
        }
        
        // 额外的全局处理确保整个内容没有多余空行
        this.processedContent = this.processedContent.replace(/\n{3,}/g, '\n\n');
        
        // 更新缓冲区
        this.lastEndChars = this.processedContent.slice(-3);
      }
    },
    // 添加对isStreaming的监听，确保状态变化时正确更新UI
    isStreaming(newValue) {
      if (!newValue) {
        console.log('AI流式消息结束，隐藏光标');
        // 强制组件重新渲染确保光标消失
        this.$forceUpdate();
      }
    }
  }
}
</script>

<style scoped>
.ai-stream-message {
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

.username {
  font-size: 12px;
  color: #666;
  margin-bottom: 2px;
}

.text {
  padding: 8px 12px;
  border-radius: 10px;
  background-color: #f1f1f1;
  word-break: break-all;
  line-height: 1.4;
  position: relative;
  min-height: 20px; /* 确保即使内容为空也有高度 */
}

.message-time {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

/* 打字光标动画 */
.cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background-color: #333;
  margin-left: 1px;
  vertical-align: middle;
  animation: blink 0.7s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 三点加载动画 */
.loading-dots {
  display: flex;
  align-items: center;
  justify-content: center;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #666;
  margin: 0 3px;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) {
  animation-delay: -0.32s;
}

.dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>