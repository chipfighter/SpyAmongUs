<template>
  <div v-if="show" class="feedback-modal-overlay" @click.self="handleClose">
    <div class="feedback-modal">
      <div class="feedback-header">
        <h2>用户反馈</h2>
        <button class="close-btn" @click="handleClose">×</button>
      </div>
      
      <div class="feedback-body">
        <!-- 反馈类型选择 -->
        <div class="feedback-section">
          <h3>反馈类型</h3>
          <div class="feedback-types">
            <div 
              v-for="type in feedbackTypes" 
              :key="type.id" 
              class="feedback-type" 
              :class="{ 'selected': selectedType === type.id }"
              @click="selectedType = type.id"
            >
              <span class="type-icon">{{ type.icon }}</span>
              <span class="type-name">{{ type.name }}</span>
            </div>
          </div>
        </div>
        
        <!-- 具体描述 -->
        <div class="feedback-section">
          <h3>具体描述</h3>
          <textarea 
            v-model="feedbackContent" 
            class="feedback-textarea" 
            placeholder="请详细描述您的反馈内容，以便我们更好地理解和处理问题..."
            :maxlength="maxContentLength"
          ></textarea>
          <div class="character-count">
            {{ feedbackContent.length }}/{{ maxContentLength }}
            <span class="min-length-hint" v-if="feedbackContent.length < 5">
              (需要至少5个字符)
            </span>
          </div>
        </div>
        
        <!-- 提交说明 -->
        <div v-if="!isValid" class="feedback-validation-hint">
          <p>提交前请确保：</p>
          <ul>
            <li :class="{ 'validated': selectedType }">选择一个反馈类型</li>
            <li :class="{ 'validated': feedbackContent.trim().length >= 5 }">输入至少5个字符的描述</li>
          </ul>
        </div>
        
        <!-- 状态提示 -->
        <div v-if="submitStatus" class="feedback-status" :class="submitStatus.type">
          <span class="status-icon">{{ submitStatus.type === 'success' ? '✓' : '✗' }}</span>
          <span class="status-message">{{ submitStatus.message }}</span>
        </div>
      </div>
      
      <div class="feedback-footer">
        <button class="cancel-btn" @click="handleClose" :disabled="isSubmitting">取消</button>
        <button 
          class="submit-btn" 
          @click="submitFeedback" 
          :disabled="!isValid || isSubmitting"
        >
          {{ isSubmitting ? '提交中...' : '提交反馈' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import axios from 'axios';
import { API_URL } from '@/config';
import { useUserStore } from '@/stores/userStore';

// 引入属性
const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  userId: {
    type: String,
    default: null
  },
  username: {
    type: String,
    default: null
  }
});

// 定义事件
const emit = defineEmits(['close', 'submit-success']);

// 反馈类型列表
const feedbackTypes = [
  { id: 'game', name: '游戏问题', icon: '🐞' },
  { id: 'feature', name: '功能建议', icon: '💡' },
  { id: 'performance', name: '性能问题', icon: '⚡' },
  { id: 'ui', name: '界面问题', icon: '🎨' },
  { id: 'other', name: '其他', icon: '📝' }
];

// 反馈数据
const selectedType = ref('');
const feedbackContent = ref('');
const maxContentLength = 500;
const isSubmitting = ref(false);
const submitStatus = ref(null);

// 验证反馈是否有效
const isValid = computed(() => {
  return selectedType.value && feedbackContent.value.trim().length >= 5;
});

// 提交反馈
const submitFeedback = async () => {
  if (!isValid.value) {
    console.error('反馈验证失败:', { type: selectedType.value, contentLength: feedbackContent.value.trim().length, minRequired: 5 });
    return;
  }
  
  try {
    isSubmitting.value = true;
    
    // 获取用户信息 - 优先使用userStore
    const userStore = useUserStore();
    
    // 优先获取store中的用户数据，这是最新和最准确的
    let userId = userStore.user?.id || 'anonymous';
    let username = userStore.user?.username || '匿名用户';
    
    // 如果用户已登录但没有在store中，尝试从localStorage获取
    if (userId === 'anonymous') {
      const userDataStr = localStorage.getItem('userData');
      const userInfoStr = localStorage.getItem('userInfo');
      
      if (userDataStr) {
        try {
          const userData = JSON.parse(userDataStr);
          userId = userData.id || userId;
          username = userData.username || username;
        } catch (e) {
          console.error('解析userData失败:', e);
        }
      } else if (userInfoStr) {
        try {
          const userInfo = JSON.parse(userInfoStr);
          userId = userInfo.id || userId;
          username = userInfo.username || username;
        } catch (e) {
          console.error('解析userInfo失败:', e);
        }
      }
    }
    
    // 使用传入的props
    if (userId === 'anonymous' && props.userId) {
      userId = props.userId;
      username = props.username || '未知用户';
    }
    
    console.log('准备提交反馈:', { 
      type: selectedType.value, 
      userId: userId, 
      username: username,
      isAuthenticated: userStore.isAuthenticated,
      hasPropsUserId: !!props.userId,
      userStoreState: !!userStore.user
    });
    
    // 准备提交的数据
    const feedbackData = {
      type: selectedType.value,
      content: feedbackContent.value.trim(),
      user_id: userId,
      username: username,
      created_at: Date.now()
    };
    
    // 获取token - 优先使用store中的token
    const accessToken = userStore.accessToken || localStorage.getItem('accessToken') || localStorage.getItem('token');
    
    // 构造请求配置
    const requestConfig = {
      withCredentials: true,
      headers: {}
    };
    
    // 添加授权头
    if (accessToken) {
      requestConfig.headers['Authorization'] = `Bearer ${accessToken}`;
      console.log('使用授权令牌:', accessToken.substring(0, 10) + '...');
    } else {
      console.warn('无可用授权令牌，反馈将以匿名方式提交');
      
      // 如果无令牌但有用户ID，提示登录可能已过期
      if (userId !== 'anonymous') {
        console.warn('有用户ID但无令牌，登录可能已过期');
        submitStatus.value = {
          type: 'error',
          message: '登录已过期，请重新登录后再提交反馈'
        };
        isSubmitting.value = false;
        return;
      }
    }
    
    // 打印详细信息
    console.log('最终提交数据:', {
      data: feedbackData,
      auth: !!accessToken,
      userStore: {
        isAuth: userStore.isAuthenticated,
        userId: userStore.user?.id,
        username: userStore.user?.username,
        hasToken: !!userStore.accessToken
      }
    });
    
    // 发送到后端
    const response = await axios.post(`${API_URL}/api/feedback/submit`, feedbackData, requestConfig);
    
    // 处理成功响应
    if (response.data.success) {
      submitStatus.value = {
        type: 'success',
        message: '反馈提交成功，感谢您的宝贵意见！'
      };
      
      // 显示感谢消息0.5秒后再关闭弹窗，不要立即重置表单
      setTimeout(() => {
        emit('submit-success');
        // 0.5秒后再关闭弹窗
        setTimeout(() => {
          handleClose();
        }, 500);
      }, 500);
    } else {
      throw new Error(response.data.message || '提交失败');
    }
  } catch (error) {
    console.error('提交反馈失败：', error);
    submitStatus.value = {
      type: 'error',
      message: error.response?.data?.message || error.message || '提交失败，请稍后重试'
    };
  } finally {
    isSubmitting.value = false;
  }
};

// 重置表单
const resetForm = () => {
  selectedType.value = '';
  feedbackContent.value = '';
  submitStatus.value = null;
};

// 处理关闭
const handleClose = () => {
  resetForm();
  emit('close');
};
</script>

<style scoped>
.feedback-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
  backdrop-filter: blur(4px);
}

.feedback-modal {
  width: 90%;
  max-width: 600px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modal-appear 0.3s ease-out;
}

@keyframes modal-appear {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.feedback-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #eee;
}

.feedback-header h2 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #333;
}

.feedback-body {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.feedback-section {
  margin-bottom: 20px;
}

.feedback-section h3 {
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 16px;
  color: #555;
  font-weight: 500;
}

.feedback-types {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.feedback-type {
  padding: 12px;
  background-color: #f5f5f5;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.feedback-type:hover {
  background-color: #eee;
}

.feedback-type.selected {
  background-color: #e6f7ff;
  border-color: #1890ff;
}

.type-icon {
  font-size: 18px;
  margin-right: 8px;
}

.feedback-textarea {
  width: 100%;
  min-height: 120px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  resize: vertical;
  font-family: inherit;
  font-size: 14px;
  transition: border-color 0.2s;
}

.feedback-textarea:focus {
  outline: none;
  border-color: #1890ff;
}

.character-count {
  text-align: right;
  margin-top: 4px;
  font-size: 12px;
  color: #999;
}

.feedback-status {
  padding: 12px;
  border-radius: 8px;
  margin-top: 12px;
  display: flex;
  align-items: center;
}

.feedback-status.success {
  background-color: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #52c41a;
}

.feedback-status.error {
  background-color: #fff2f0;
  border: 1px solid #ffccc7;
  color: #ff4d4f;
}

.status-icon {
  margin-right: 8px;
  font-weight: bold;
}

.feedback-footer {
  padding: 15px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid #eee;
}

.cancel-btn {
  padding: 8px 16px;
  background-color: #f5f5f5;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.cancel-btn:hover {
  background-color: #e8e8e8;
}

.submit-btn {
  padding: 8px 16px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.submit-btn:hover {
  background-color: #40a9ff;
}

.submit-btn:disabled {
  background-color: #bae7ff;
  cursor: not-allowed;
}

.min-length-hint {
  color: #ff4d4f;
  margin-left: 8px;
  font-size: 12px;
}

.feedback-validation-hint {
  padding: 10px;
  background-color: #fff7e6;
  border: 1px solid #ffe58f;
  border-radius: 6px;
  margin-bottom: 15px;
}

.feedback-validation-hint p {
  margin: 0 0 5px 0;
  font-weight: 500;
  color: #d48806;
}

.feedback-validation-hint ul {
  margin: 0;
  padding-left: 20px;
}

.feedback-validation-hint li {
  color: #666;
}

.feedback-validation-hint li.validated {
  color: #52c41a;
}
</style> 