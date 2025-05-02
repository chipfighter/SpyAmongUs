<template>
  <div class="profile-page">
    <div class="profile-container">
      <!-- 顶部导航栏 -->
      <div class="profile-header">
        <button @click="backToLobby" class="back-button">
          <span class="back-icon">←</span> 返回大厅
        </button>
        <h1 class="profile-title">个人信息</h1>
      </div>
      
      <!-- 内容区域 -->
      <div class="profile-content">
        <!-- 左侧头像区 -->
        <div class="profile-sidebar">
          <div class="avatar-container">
            <img 
              :src="previewAvatar || userStore.userAvatar" 
              alt="用户头像" 
              class="profile-avatar" 
              @error="onAvatarError"
            >
            <button @click="selectAvatar" class="avatar-edit-btn">
              <span class="edit-icon">📷</span>
            </button>
          </div>
          
          <div class="username-display">
            <span class="label">用户名</span>
            <h2 class="value">{{ userInfo.username }}</h2>
          </div>
          
          <div class="avatar-actions" v-if="avatarChanged">
            <div v-if="avatarSuccess" class="success-message">
              <span class="success-icon">✓</span> 头像更新成功
            </div>
            <div v-if="avatarError" class="error-message">
              <span class="error-icon">✗</span> {{ avatarError }}
            </div>
            
            <button 
              @click="saveAvatar" 
              class="primary-button avatar-save-btn" 
              :disabled="isAvatarUploading"
            >
              {{ isAvatarUploading ? '上传中...' : '保存头像' }}
            </button>
          </div>
          
          <input 
            type="file" 
            ref="avatarInput" 
            style="display: none" 
            accept="image/*" 
            @change="handleAvatarChange"
          >
        </div>
        
        <!-- 右侧信息表单 -->
        <div class="profile-info">
          <!-- 账户信息区域 -->
          <div class="info-card">
            <div class="card-header">
              <h3 class="card-title">
                <span class="card-icon">🔑</span> 账户信息
              </h3>
            </div>
            
            <div class="card-body">
              <div class="info-item">
                <span class="info-label">用户ID</span>
                <span class="info-value id-value">{{ userInfo.id }}</span>
              </div>
              
              <div class="info-divider"></div>
              
              <div class="info-item">
                <span class="info-label">注册时间</span>
                <span class="info-value">{{ formatDate(userInfo.createdAt) }}</span>
              </div>
            </div>
          </div>
          
          <!-- 密码修改区域 -->
          <div class="info-card">
            <div class="card-header">
              <h3 class="card-title">
                <span class="card-icon">🔒</span> 修改密码
              </h3>
            </div>
            
            <div class="card-body">
              <div class="form-group">
                <label for="currentPassword" class="form-label">当前密码</label>
                <div class="input-container">
                  <input 
                    type="password" 
                    id="currentPassword" 
                    class="form-input" 
                    v-model="passwordData.currentPassword"
                    placeholder="输入当前密码"
                  >
                </div>
              </div>
              
              <div class="form-group">
                <label for="newPassword" class="form-label">新密码</label>
                <div class="input-container">
                  <input 
                    type="password" 
                    id="newPassword" 
                    class="form-input" 
                    v-model="passwordData.newPassword"
                    placeholder="输入新密码"
                  >
                </div>
              </div>
              
              <div class="form-group">
                <label for="confirmPassword" class="form-label">确认新密码</label>
                <div class="input-container">
                  <input 
                    type="password" 
                    id="confirmPassword" 
                    class="form-input" 
                    v-model="passwordData.confirmPassword"
                    placeholder="再次输入新密码"
                  >
                </div>
              </div>
              
              <div v-if="passwordSuccess || passwordError" class="message-container">
                <div v-if="passwordSuccess" class="success-message">
                  <span class="success-icon">✓</span> 密码修改成功
                </div>
                <div v-if="passwordError" class="error-message">
                  <span class="error-icon">✗</span> {{ passwordError }}
                </div>
              </div>
              
              <button 
                @click="updatePassword" 
                class="primary-button"
                :disabled="isPasswordUpdating || !canUpdatePassword"
              >
                {{ isPasswordUpdating ? '更新中...' : '更新密码' }}
              </button>
            </div>
          </div>
          
          <!-- 游戏统计区域（占位）-->
          <div class="info-card">
            <div class="card-header">
              <h3 class="card-title">
                <span class="card-icon">📊</span> 游戏统计
              </h3>
              <span class="badge">即将推出</span>
            </div>
            
            <div class="card-body disabled-content">
              <div class="placeholder-text">游戏统计功能即将上线，敬请期待！</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/userStore'

const router = useRouter()
const userStore = useUserStore()

// 用户基本信息
const userInfo = ref({
  id: '',
  username: '',
  createdAt: new Date()
})

// 头像上传相关
const avatarInput = ref(null)
const previewAvatar = ref(null)
const avatarChanged = ref(false)
const isAvatarUploading = ref(false)
const avatarSuccess = ref(false)
const avatarError = ref(null)

// 密码修改相关
const passwordData = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const isPasswordUpdating = ref(false)
const passwordSuccess = ref(false)
const passwordError = ref(null)

// 格式化日期
const formatDate = (date) => {
  if (!date) return '未知'
  
  const d = new Date(date)
  if (isNaN(d.getTime())) return '未知'
  
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

// 计算属性：是否可以更新密码
const canUpdatePassword = computed(() => {
  return (
    passwordData.value.currentPassword.length > 0 &&
    passwordData.value.newPassword.length >= 6 &&
    passwordData.value.newPassword === passwordData.value.confirmPassword
  )
})

// 初始化页面
onMounted(() => {
  // 从store获取用户信息
  if (userStore.user) {
    userInfo.value = {
      id: userStore.user.id,
      username: userStore.user.username,
      createdAt: userStore.user.createdAt || new Date()
    }
  } else {
    // 如果没有用户信息，重定向到登录页
    router.push('/login')
  }
})

// 处理头像错误
const onAvatarError = (e) => {
  e.target.src = '/default_avatar.jpg'
}

// 返回大厅
const backToLobby = () => {
  router.push('/lobby')
}

// 选择头像
const selectAvatar = () => {
  avatarInput.value.click()
}

// 处理头像变更
const handleAvatarChange = (e) => {
  const file = e.target.files[0]
  if (!file) return
  
  // 验证文件类型
  if (!file.type.match('image.*')) {
    avatarError.value = '请选择图片文件'
    return
  }
  
  // 验证文件大小 (最大2MB)
  if (file.size > 2 * 1024 * 1024) {
    avatarError.value = '图片大小不能超过2MB'
    return
  }
  
  // 创建文件预览
  const reader = new FileReader()
  reader.onload = (e) => {
    previewAvatar.value = e.target.result
    avatarChanged.value = true
    avatarSuccess.value = false
    avatarError.value = null
  }
  reader.readAsDataURL(file)
}

// 保存头像
const saveAvatar = async () => {
  if (!previewAvatar.value) return
  
  isAvatarUploading.value = true
  avatarError.value = null
  
  try {
    // 调用store方法更新头像
    const success = await userStore.updateAvatar(userInfo.value.id, previewAvatar.value)
    
    if (success) {
      avatarSuccess.value = true
      avatarChanged.value = false
    } else {
      avatarError.value = userStore.error || '头像更新失败'
    }
  } catch (error) {
    avatarError.value = error.message || '头像更新失败'
  } finally {
    isAvatarUploading.value = false
  }
}

// 更新密码
const updatePassword = async () => {
  // 验证两次输入的密码是否一致
  if (passwordData.value.newPassword !== passwordData.value.confirmPassword) {
    passwordError.value = '两次输入的密码不一致'
    return
  }
  
  // 验证新密码长度
  if (passwordData.value.newPassword.length < 6) {
    passwordError.value = '新密码长度至少为6个字符'
    return
  }
  
  isPasswordUpdating.value = true
  passwordError.value = null
  
  try {
    const success = await userStore.updatePassword(
      userInfo.value.id,
      passwordData.value.currentPassword,
      passwordData.value.newPassword
    )
    
    if (success) {
      passwordSuccess.value = true
      // 清空密码输入框
      passwordData.value = {
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      }
    } else {
      passwordError.value = userStore.error || '密码更新失败'
    }
  } catch (error) {
    passwordError.value = error.message || '密码更新失败'
  } finally {
    isPasswordUpdating.value = false
  }
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background-color: #f5f7fa;
  padding: 20px;
}

.profile-container {
  max-width: 1000px;
  margin: 0 auto;
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 2px 20px rgba(0,0,0,0.1);
  overflow: hidden;
}

/* 头部样式 */
.profile-header {
  display: flex;
  align-items: center;
  padding: 20px 30px;
  background-color: #4a6cf7;
  color: white;
  position: relative;
}

.profile-title {
  margin: 0 auto;
  font-size: 24px;
  font-weight: 600;
}

.back-button {
  display: flex;
  align-items: center;
  background: rgba(255,255,255,0.2);
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 15px;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-button:hover {
  background: rgba(255,255,255,0.3);
}

.back-icon {
  margin-right: 8px;
  font-weight: bold;
}

/* 内容区样式 */
.profile-content {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 25px;
  padding: 30px;
}

/* 左侧边栏样式 */
.profile-sidebar {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.avatar-container {
  position: relative;
  width: 180px;
  height: 180px;
  margin-bottom: 20px;
}

.profile-avatar {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid #4a6cf7;
  box-shadow: 0 4px 15px rgba(74, 108, 247, 0.2);
  background-color: #eee;
}

.avatar-edit-btn {
  position: absolute;
  bottom: 10px;
  right: 10px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #4a6cf7;
  color: white;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  transition: all 0.2s;
}

.avatar-edit-btn:hover {
  transform: scale(1.1);
  background-color: #3a5ce5;
}

.edit-icon {
  font-size: 18px;
}

.username-display {
  width: 100%;
  text-align: center;
  margin-bottom: 20px;
}

.username-display .label {
  display: block;
  color: #777;
  font-size: 14px;
  margin-bottom: 5px;
}

.username-display .value {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.avatar-save-btn {
  margin-top: 15px;
  width: 100%;
}

/* 右侧信息区样式 */
.profile-info {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.info-card {
  background-color: white;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
  overflow: hidden;
  border: 1px solid #eee;
}

.card-header {
  padding: 15px 20px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
}

.card-icon {
  margin-right: 10px;
  font-size: 18px;
}

.badge {
  background-color: #f1c40f;
  color: #333;
  padding: 3px 8px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.card-body {
  padding: 20px;
}

.info-item {
  display: flex;
  align-items: center;
  padding: 10px 0;
}

.info-label {
  flex: 0 0 100px;
  color: #666;
  font-size: 14px;
}

.info-value {
  font-size: 15px;
  color: #333;
}

.id-value {
  font-family: monospace;
  background-color: #f5f5f5;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 13px;
}

.info-divider {
  height: 1px;
  background-color: #eee;
  margin: 10px 0;
}

/* 表单样式 */
.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #555;
  font-size: 14px;
}

.input-container {
  position: relative;
}

.form-input {
  width: 100%;
  padding: 12px 15px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  background-color: #f9f9f9;
  transition: all 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: #4a6cf7;
  background-color: white;
  box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.1);
}

/* 按钮样式 */
.primary-button {
  padding: 12px 20px;
  background-color: #4a6cf7;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: block;
}

.primary-button:hover {
  background-color: #3a5ce5;
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(74, 108, 247, 0.2);
}

.primary-button:active {
  transform: translateY(0);
}

.primary-button:disabled {
  background-color: #a8b8f8;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 消息样式 */
.message-container {
  margin-bottom: 15px;
}

.success-message, .error-message {
  padding: 10px 15px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.success-message {
  background-color: rgba(39, 174, 96, 0.1);
  color: #27ae60;
  border-left: 3px solid #27ae60;
}

.error-message {
  background-color: rgba(231, 76, 60, 0.1);
  color: #e74c3c;
  border-left: 3px solid #e74c3c;
}

.success-icon, .error-icon {
  margin-right: 10px;
  font-weight: bold;
}

/* 禁用内容 */
.disabled-content {
  opacity: 0.7;
  pointer-events: none;
}

.placeholder-text {
  text-align: center;
  padding: 30px 0;
  color: #777;
  font-style: italic;
}

/* 响应式设计 */
@media (max-width: 900px) {
  .profile-content {
    grid-template-columns: 1fr;
  }
  
  .profile-sidebar {
    margin-bottom: 20px;
  }
}

@media (max-width: 600px) {
  .profile-header {
    flex-direction: column;
    gap: 15px;
    padding: 15px;
  }
  
  .back-button {
    position: static;
    margin-bottom: 10px;
  }
  
  .profile-content {
    padding: 15px;
  }
}
</style> 