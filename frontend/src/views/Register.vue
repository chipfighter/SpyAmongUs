<template>
  <div class="register-container">
    <div class="register-box">
      <h1>间谍游戏</h1>
      <h2>用户注册</h2>
      
      <div v-if="error" class="error-message">
        {{ error }}
      </div>
      
      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label for="username">用户名</label>
          <input 
            id="username" 
            v-model="username" 
            type="text" 
            placeholder="请输入用户名"
            required
          />
        </div>
        
        <div class="form-group">
          <label for="password">密码</label>
          <input 
            id="password" 
            v-model="password" 
            type="password" 
            placeholder="请输入密码"
            required
          />
        </div>
        
        <div class="form-group">
          <label for="confirmPassword">确认密码</label>
          <input 
            id="confirmPassword" 
            v-model="confirmPassword" 
            type="password" 
            placeholder="再次输入密码"
            required
          />
        </div>
        
        <div class="form-actions">
          <button 
            type="submit" 
            class="btn-primary" 
            :disabled="loading"
          >
            {{ loading ? '注册中...' : '注册' }}
          </button>
          
          <router-link to="/login" class="btn-link">
            已有账号？返回登录
          </router-link>
        </div>
        
        <div v-if="statusMessage" class="status-message">
          {{ statusMessage }}
        </div>
        
        <div class="service-status" :class="{ error: !backendAvailable }">
          后端服务状态: {{ backendAvailable ? '可用' : '不可用' }}
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { userStore } from '../store/user'

// API基础URL常量
const API_BASE_URL = 'http://127.0.0.1:8000';

export default {
  name: 'RegisterView',
  
  setup() {
    const router = useRouter()
    const username = ref('')
    const password = ref('')
    const confirmPassword = ref('')
    const error = ref('')
    const loading = ref(false)
    const statusMessage = ref('')
    const backendAvailable = ref(false)
    
    // 检查后端服务状态
    const checkBackendStatus = async () => {
      console.log('检查后端服务状态...');
      try {
        const response = await fetch(`${API_BASE_URL}/`);
        backendAvailable.value = response.ok;
        console.log(`后端服务状态: ${response.ok ? '可用' : '不可用'}, 响应状态: ${response.status}`);
        
        if (!response.ok) {
          error.value = '后端服务不可用，请检查服务是否启动';
          console.error('后端服务不可用');
        }
      } catch (e) {
        backendAvailable.value = false;
        error.value = '无法连接到后端服务';
        console.error('后端服务检查出错:', e);
      }
    };
    
    // 处理注册
    const handleRegister = async () => {
      console.log(`尝试注册，用户名: ${username.value}, 密码长度: ${password.value ? password.value.length : 0}`);
      error.value = '';
      
      // 验证输入
      if (!username.value || username.value.trim() === '') {
        error.value = '用户名不能为空';
        console.error('注册失败: 用户名为空');
        return;
      }
      
      if (!password.value) {
        error.value = '密码不能为空';
        console.error('注册失败: 密码为空');
        return;
      }
      
      if (password.value.length < 6) {
        error.value = '密码长度必须至少为6位';
        console.error('注册失败: 密码长度不足6位');
        return;
      }
      
      if (password.value !== confirmPassword.value) {
        error.value = '两次输入的密码不一致';
        console.error('注册失败: 两次输入的密码不一致');
        return;
      }
      
      // 检查后端服务状态
      await checkBackendStatus();
      if (!backendAvailable.value) {
        error.value = '后端服务不可用，请确保服务已启动';
        console.error('注册失败: 后端服务不可用');
        return;
      }
      
      loading.value = true;
      statusMessage.value = '正在注册...';
      
      try {
        console.log('调用用户存储register方法');
        const user = await userStore.register(username.value, password.value);
        
        if (user) {
          console.log('注册成功，用户信息:', user);
          statusMessage.value = '注册成功，正在跳转...';
          
          // 导航到游戏大厅
          setTimeout(() => {
            router.push('/lobby');
          }, 500);
        } else {
          error.value = userStore.error || '注册失败，请尝试其他用户名';
          console.error('注册失败:', userStore.error);
          
          // 清除可能的无效用户数据
          localStorage.removeItem('user');
        }
      } catch (e) {
        console.error('注册过程出错:', e);
        error.value = e.message || '注册时发生错误';
      } finally {
        loading.value = false;
      }
    };
    
    // 页面加载时执行
    onMounted(async () => {
      // 恢复会话（如果有）
      if (userStore.restoreSession()) {
        console.log('从localStorage恢复了用户会话，正在跳转到大厅');
        router.push('/lobby');
        return;
      }
      
      // 检查后端服务状态
      await checkBackendStatus();
    });
    
    return {
      username,
      password,
      confirmPassword,
      error,
      loading,
      statusMessage,
      backendAvailable,
      handleRegister
    }
  }
}
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
}

.register-box {
  width: 100%;
  max-width: 400px;
  padding: 30px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

h1 {
  text-align: center;
  color: #333;
  margin-bottom: 10px;
}

h2 {
  text-align: center;
  color: #555;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 20px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #555;
}

input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 30px;
}

.btn-primary {
  background-color: #4CAF50;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  transition: background-color 0.3s;
}

.btn-primary:hover {
  background-color: #45a049;
}

.btn-primary:disabled {
  background-color: #aaa;
  cursor: not-allowed;
}

.btn-link {
  color: #2196F3;
  text-decoration: none;
}

.btn-link:hover {
  text-decoration: underline;
}

.error-message {
  background-color: #ffebee;
  color: #d32f2f;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.status-message {
  margin-top: 20px;
  text-align: center;
  color: #4CAF50;
}

.service-status {
  margin-top: 10px;
  font-size: 12px;
  color: #666;
  text-align: center;
}

.service-status.error {
  color: #d32f2f;
}
</style> 