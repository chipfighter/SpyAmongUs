<template>
  <div class="register-container">
    <div class="register-card">
      <div class="card-header">
        <h1 class="title">谁是卧底</h1>
        <div class="subtitle">创建新账号</div>
      </div>
      
      <div v-if="userStore.error" class="error-message">
        {{ userStore.error }}
      </div>
      
      <form @submit.prevent="handleRegister" class="register-form">
        <div class="form-group">
          <label for="username">用户名</label>
          <div class="input-wrapper">
            <input 
              id="username" 
              v-model="username" 
              type="text" 
              required 
              placeholder="请输入用户名"
              :disabled="userStore.loading"
            />
            <i class="icon user-icon">👤</i>
          </div>
        </div>
        
        <div class="form-group">
          <label for="password">密码</label>
          <div class="input-wrapper">
            <input 
              id="password" 
              v-model="password" 
              :type="showPassword ? 'text' : 'password'" 
              required 
              placeholder="请输入密码"
              :disabled="userStore.loading"
            />
            <i 
              class="icon password-icon" 
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? '👁️' : '🔒' }}
            </i>
          </div>
        </div>
        
        <div class="form-group">
          <label for="confirmPassword">确认密码</label>
          <div class="input-wrapper">
            <input 
              id="confirmPassword" 
              v-model="confirmPassword" 
              :type="showConfirmPassword ? 'text' : 'password'" 
              required 
              placeholder="请再次输入密码"
              :disabled="userStore.loading"
            />
            <i 
              class="icon password-icon" 
              @click="showConfirmPassword = !showConfirmPassword"
            >
              {{ showConfirmPassword ? '👁️' : '🔒' }}
            </i>
          </div>
          <div class="password-mismatch" v-if="passwordMismatch">
            两次输入的密码不匹配
          </div>
        </div>
        
        <button 
          type="submit" 
          class="register-button" 
          :disabled="userStore.loading || passwordMismatch"
        >
          {{ userStore.loading ? '注册中...' : '注册' }}
        </button>
      </form>
      
      <div class="login-link">
        已有账号？ 
        <router-link to="/login" class="highlight">返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/userStore'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)

// 验证密码是否匹配
const passwordMismatch = computed(() => {
  return confirmPassword.value && password.value !== confirmPassword.value
})

async function handleRegister() {
  if (!username.value || !password.value || !confirmPassword.value) return
  if (passwordMismatch.value) return
  
  const success = await userStore.register(username.value, password.value)
  if (success) {
    router.push('/lobby')
  }
}
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f8f9fa;
  padding: 1rem;
}

.register-card {
  background-color: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  padding: 3rem;
  width: 100%;
  max-width: 420px;
  animation: fadeIn 0.6s ease-out;
  backdrop-filter: blur(10px);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-20px); }
  to { opacity: 1; transform: translateY(0); }
}

.card-header {
  text-align: center;
  margin-bottom: 2.5rem;
}

.title {
  color: #000000;
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
  font-weight: 700;
}

.subtitle {
  color: #6c757d;
  font-size: 1.1rem;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 1.8rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-weight: 600;
  color: #4a4a4a;
  font-size: 0.95rem;
}

.input-wrapper {
  position: relative;
}

.input-wrapper input {
  width: 100%;
  padding: 0.9rem 1rem;
  padding-right: 2.5rem;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  transition: all 0.2s;
}

.input-wrapper input:focus {
  outline: none;
  border-color: #3b71ca;
  box-shadow: 0 0 0 3px rgba(59, 113, 202, 0.25);
}

.icon {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #6c757d;
  cursor: pointer;
  font-style: normal;
}

.password-icon {
  cursor: pointer;
}

.password-icon:hover {
  color: #3b71ca;
}

.register-button {
  background: linear-gradient(to right, #3b71ca, #6a11cb);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 1rem;
  font-size: 1.05rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 0.5rem;
}

.register-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(59, 113, 202, 0.4);
}

.register-button:disabled {
  background: #a0b4d5;
  cursor: not-allowed;
}

.login-link {
  margin-top: 2rem;
  text-align: center;
  color: #6c757d;
  font-size: 1rem;
}

.login-link .highlight {
  color: #3b71ca;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.2s;
}

.login-link .highlight:hover {
  color: #6a11cb;
  text-decoration: underline;
}

.error-message {
  background-color: #fff5f5;
  color: #e53e3e;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
  border-left: 4px solid #e53e3e;
}

.password-mismatch {
  color: #e53e3e;
  font-size: 0.85rem;
  margin-top: 0.5rem;
  font-weight: 500;
}

@media (max-width: 768px) {
  .register-card {
    padding: 2rem;
  }
}

/* 通用容器 */
.input-wrapper input[type="password"]::-ms-reveal,
.input-wrapper input[type="password"]::-ms-clear,                      /* Edge 旧版 */
.input-wrapper input[type="password"]::-webkit-credentials-auto-fill-button,
.input-wrapper input[type="password"]::-webkit-contacts-auto-fill-button, /* Chrome/Safari */
.input-wrapper input[type="password"]::placeholder,
.input-wrapper input[type="password"]::-webkit-input-placeholder,
.input-wrapper input[type="password"]:-ms-input-placeholder {
  display: none !important;
  pointer-events: none;
  visibility: hidden;
}

/* 强制隐藏所有 WebKit 自动填充按钮 */
input[type="password"]::-webkit-credentials-auto-fill-button,
input[type="password"]::-webkit-contacts-auto-fill-button {
  display: none !important;
  visibility: hidden;
  pointer-events: none;
  height: 0;
  width: 0;
  margin: 0;
  padding: 0;
}

/* 针对 Edge（新版和旧版） */
input[type="password"]::-ms-reveal,
input[type="password"]::-ms-clear {
  display: none !important;
  pointer-events: none;
  visibility: hidden;
}

/* 自定义图标层级 */
.password-icon {
  z-index: 2;
}

</style> 