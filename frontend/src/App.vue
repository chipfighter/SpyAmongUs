<template>
  <RouterView />
</template>

<script setup>
import { RouterView } from 'vue-router'
import { onMounted } from 'vue'
import { useUserStore } from './stores/userStore'
import { useRouter } from 'vue-router'

const userStore = useUserStore()
const router = useRouter()

onMounted(async () => {
  // 初始化用户状态
  userStore.initStore()
  userStore.setAuthHeader()
  
  // 如果本地有用户缓存，检查会话是否存在（处理断线重连）
  if (userStore.user && userStore.user.id) {
    const sessionExists = await userStore.checkSessionExists()
    if (!sessionExists) {
      // 会话不存在，清理本地缓存并重定向到登录页
      userStore.clearUserData()
      router.push('/login')
    }
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