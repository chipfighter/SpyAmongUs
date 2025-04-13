<template>
  <RouterView />
</template>

<script setup>
import { RouterView } from 'vue-router'
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useUserStore } from './stores/userStore'
import { useRouter } from 'vue-router'

const userStore = useUserStore()
const router = useRouter()
const sessionCheckTimer = ref(null)

// 会话检查间隔（10分钟）
const SESSION_CHECK_INTERVAL = 10 * 60 * 1000

// 初始化用户会话
const initUserSession = async () => {
  console.log('初始化用户会话...')
  
  // 从本地存储加载用户状态
  userStore.initStore()
  
  // 如果找到用户凭证，验证会话是否有效
  if (userStore.isAuthenticated) {
    try {
      const sessionExists = await userStore.checkSessionExists()
      if (!sessionExists) {
        console.warn('会话已过期或不存在，重定向到登录页')
        router.push('/login')
      } else {
        console.log('会话有效，已登录')
      }
    } catch (error) {
      console.error('会话验证失败:', error)
      userStore.clearUserData()
      router.push('/login')
    }
  } else {
    console.log('未找到用户凭证，保持当前页面')
  }
}

// 定期检查会话状态
const checkUserSession = async () => {
  if (userStore.isAuthenticated) {
    try {
      const sessionExists = await userStore.checkSessionExists()
      if (!sessionExists) {
        console.warn('定期检查：会话已过期，重定向到登录页')
        router.push('/login')
      }
    } catch (error) {
      console.error('定期会话检查失败:', error)
    }
  }
}

onMounted(async () => {
  // 初次加载时验证会话
  await initUserSession()
  
  // 设置定期检查
  sessionCheckTimer.value = setInterval(checkUserSession, SESSION_CHECK_INTERVAL)
})

onBeforeUnmount(() => {
  // 清除定时器
  if (sessionCheckTimer.value) {
    clearInterval(sessionCheckTimer.value)
    sessionCheckTimer.value = null
  }
})
</script>

<style>
/* 全局样式 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Helvetica Neue', Arial, sans-serif;
  color: #333;
  line-height: 1.6;
}

#app {
  width: 100%;
  height: 100vh;
}

:root {
  --primary-color: #3b71ca;
  --secondary-color: #6c757d;
  --success-color: #28a745;
  --danger-color: #dc3545;
  --light-color: #f5f7fa;
  --dark-color: #495057;
}
</style>