<template>
  <div class="login-container">
    <div class="login-box">
      <h1>间谍游戏</h1>
      <h2>用户登录</h2>
      
      <div v-if="error" class="error-message">
        {{ error }}
      </div>
      
      <form @submit.prevent="handleLogin">
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
        
        <div class="form-actions">
          <button 
            type="submit" 
            class="btn-primary" 
            :disabled="loading"
          >
            {{ loading ? '登录中...' : '登录' }}
          </button>
          
          <router-link to="/register" class="btn-link">
            没有账号？立即注册
          </router-link>
        </div>
        
        <div v-if="statusMessage" class="status-message">
          {{ statusMessage }}
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { userStore } from '../store/user'

export default {
  name: 'LoginView',
  
  setup() {
    const router = useRouter()
    const username = ref('')
    const password = ref('')
    const error = ref('')
    const loading = ref(false)
    const statusMessage = ref('')
    
    // 处理登录
    const handleLogin = async () => {
      error.value = '';
      statusMessage.value = '';
      
      // 检查输入
      if (!username.value || username.value.trim() === '') {
        error.value = '用户名不能为空';
        return;
      }
      
      if (!password.value) {
        error.value = '密码不能为空';
        return;
      }
      
      loading.value = true;
      statusMessage.value = '正在登录...';
      
      try {
        const user = await userStore.loginWithPassword(username.value, password.value);
        
        if (user) {
          statusMessage.value = '登录成功，正在跳转...';
          
          // 直接跳转到游戏大厅
          router.push('/lobby');
        } else {
          error.value = userStore.error || '登录失败，请检查用户名和密码';
          statusMessage.value = '';
          
          // 清除可能的无效用户数据
          localStorage.removeItem('user');
        }
      } catch (e) {
        error.value = e.message || '登录时发生错误';
        statusMessage.value = '';
      } finally {
        loading.value = false;
      }
    };
    
    return {
      username,
      password,
      error,
      loading,
      statusMessage,
      handleLogin
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
}

.login-box {
  width: 100%;
  max-width: 400px;
  padding: 2rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

h1 {
  text-align: center;
  color: #2c3e50;
  margin-bottom: 0.5rem;
}

h2 {
  text-align: center;
  color: #7f8c8d;
  margin-bottom: 2rem;
  font-weight: normal;
  font-size: 1.2rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  color: #34495e;
}

input {
  width: 100%;
  padding: 0.8rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 2rem;
}

.btn-primary {
  background-color: #3498db;
  color: white;
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  transition: background-color 0.3s;
}

.btn-primary:hover {
  background-color: #2980b9;
}

.btn-primary:disabled {
  background-color: #95a5a6;
  cursor: not-allowed;
}

.btn-link {
  color: #3498db;
  text-decoration: none;
}

.btn-link:hover {
  text-decoration: underline;
}

.error-message {
  background-color: #f8d7da;
  color: #721c24;
  padding: 0.8rem;
  border-radius: 4px;
  margin-bottom: 1.5rem;
}

.status-message {
  text-align: center;
  margin-top: 1rem;
  color: #7f8c8d;
}
</style> 