import { defineStore } from 'pinia'
import axios from 'axios'
import { API_URL } from '@/config'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    accessToken: null,
    refreshToken: null,
    loading: false,
    error: null,
    lastActivityTime: Date.now(),
    tokenRefreshTimer: null
  }),
  
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    userAvatar: (state) => state.user?.avatar_url || '/default_avatar.jpg',
    isSessionExpired: (state) => {
      if (!state.lastActivityTime) return true
      const inactiveTime = Date.now() - state.lastActivityTime
      return inactiveTime > 24 * 60 * 1000
    }
  },
  
  actions: {
    updateActivityTime() {
      this.lastActivityTime = Date.now()
      localStorage.setItem('lastActivityTime', this.lastActivityTime.toString())
    },
    
    initStore() {
      const accessToken = localStorage.getItem('accessToken')
      const refreshToken = localStorage.getItem('refreshToken')
      const userData = localStorage.getItem('userData')
      const lastActivityTime = localStorage.getItem('lastActivityTime')
      
      if (accessToken && userData) {
        this.accessToken = accessToken
        this.refreshToken = refreshToken
        this.user = JSON.parse(userData)
        this.lastActivityTime = lastActivityTime ? parseInt(lastActivityTime) : Date.now()
        // 初始化后启动token刷新定时器
        this.startTokenRefreshTimer()
      }
    },
    
    saveUserData() {
      if (this.accessToken) {
        // 统一使用accessToken作为key
        localStorage.setItem('accessToken', this.accessToken)
        localStorage.setItem('token', this.accessToken)  // 为了兼容性保留
        localStorage.setItem('refreshToken', this.refreshToken || '')
        localStorage.setItem('userData', JSON.stringify(this.user))
        localStorage.setItem('lastActivityTime', this.lastActivityTime.toString())
        // 同时将userInfo存储为与RoomView中使用的格式一致
        localStorage.setItem('userInfo', JSON.stringify({
          id: this.user.id,
          username: this.user.username,
          user_name: this.user.username,
          avatar_url: this.user.avatar_url
        }))
      }
    },
    
    startTokenRefreshTimer() {
      // 清除现有定时器
      if (this.tokenRefreshTimer) {
        clearInterval(this.tokenRefreshTimer)
      }
      
      // 每20分钟刷新一次token（access_token有效期25分钟）
      this.tokenRefreshTimer = setInterval(async () => {
        if (this.isAuthenticated) {
          await this.refreshAccessToken()
        }
      }, 20 * 60 * 1000)
    },
    
    stopTokenRefreshTimer() {
      if (this.tokenRefreshTimer) {
        clearInterval(this.tokenRefreshTimer)
        this.tokenRefreshTimer = null
      }
    },
    
    async login(username, password) {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.post(`${API_URL}/api/login`, { username, password })
        
        if (response.data.success) {
          const { data } = response.data
          // 将整个用户数据设置到user中
          this.user = {
            id: data.id,
            username: data.username,
            user_name: data.username,
            avatar_url: data.avatar_url,
            status: data.status,
            current_room: data.current_room,
            statistics: data.statistics,
            style_profile: data.style_profile
          }
          this.accessToken = data.access_token
          this.refreshToken = data.refresh_token
          
          // 同时设置localStorage中的token键，以匹配路由守卫
          localStorage.setItem('token', data.access_token)
          
          this.updateActivityTime()
          this.saveUserData()
          // 登录成功后启动token刷新定时器
          this.startTokenRefreshTimer()
          return true
        } else {
          this.error = response.data.message
          return false
        }
      } catch (error) {
        this.error = error.response?.data?.message || '登录失败，请稍后再试'
        return false
      } finally {
        this.loading = false
      }
    },
    
    async register(username, password) {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.post(`${API_URL}/api/register`, { username, password })
        
        if (response.data.success) {
          const { data } = response.data;
          // 解构需要的用户数据
          this.user = {
            id: data.user_data.id,
            username: data.user_data.username,
            user_name: data.user_data.username,
            avatar_url: data.user_data.avatar_url,
            status: data.user_data.status,
            current_room: data.user_data.current_room,
            statistics: data.user_data.statistics || {},
            style_profile: data.user_data.style_profile || {}
          }
          this.accessToken = data.user_data.access_token
          this.refreshToken = data.user_data.refresh_token
          
          // 同时设置localStorage中的token键，以匹配路由守卫
          localStorage.setItem('token', data.user_data.access_token)
          
          this.updateActivityTime()
          this.saveUserData()
          // 注册成功后启动token刷新定时器
          this.startTokenRefreshTimer()
          return true
        } else {
          this.error = response.data.message
          return false
        }
      } catch (error) {
        this.error = error.response?.data?.message || '注册失败，请稍后再试'
        return false
      } finally {
        this.loading = false
      }
    },
    
    async logout() {
      this.loading = true;
      this.error = null;
      
      try {
        // 停止token刷新定时器
        this.stopTokenRefreshTimer();
        
        // 保存当前的token用于请求
        const token = this.accessToken;
        const userId = this.user?.id;
        
        console.log('准备登出用户:', userId);
        
        if (token && userId) {
          try {
            console.log('发送登出请求，使用token:', token.substring(0, 10) + '...');
            
            // 先发送请求到后端，让服务器清理会话
            const response = await axios({
              method: 'post',
              url: `${API_URL}/api/logout`,
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              },
              data: {},
              timeout: 5000
            });
            
            console.log('登出响应:', response.data);
          } catch (apiError) {
            console.error('服务器登出请求失败:', apiError.response?.data?.message || apiError.message);
          }
        } else {
          console.warn('登出缺少必要信息:', { hasToken: !!token, hasUserId: !!userId });
        }
        
        // 无论服务器请求成功与否，都清理本地状态
        this.clearUserData();
        console.log('用户本地状态已清理');
        
      } catch (error) {
        console.error('登出过程中发生错误:', error);
        // 确保在出错时也能清理本地状态
        this.clearUserData();
      } finally {
        this.loading = false;
      }
      
      return true;
    },
    
    clearUserData() {
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      this.lastActivityTime = null
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('userData')
      localStorage.removeItem('lastActivityTime')
      // 同时清除与路由守卫相关的token
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      // 停止token刷新定时器
      this.stopTokenRefreshTimer()
    },
    
    async checkUserStatus() {
      if (!this.user?.id || !this.accessToken) return false
      
      try {
        const response = await axios.get(`${API_URL}/api/user/${this.user.id}`)
        if (response.data.success) {
          this.updateActivityTime()
          return true
        }
        return false
      } catch (error) {
        if (error.response?.status === 401) {
          // 尝试刷新token
          const refreshed = await this.refreshAccessToken()
          if (!refreshed) {
            this.clearUserData()
          }
          return refreshed
        }
        return false
      }
    },
    
    async checkSessionExists() {
      if (!this.user?.id) return false
      
      try {
        const response = await axios.get(`${API_URL}/api/user/${this.user.id}/session`)
        
        if (response.data.success) {
          const sessionExists = response.data.data.session_exists
          
          if (sessionExists) {
            this.updateActivityTime()
            return true
          } else {
            this.clearUserData()
            return false
          }
        }
        return false
      } catch (error) {
        console.error('检查用户会话失败:', error)
        if (error.response?.status === 401) {
          // 尝试刷新token
          const refreshed = await this.refreshAccessToken()
          if (!refreshed) {
            this.clearUserData()
          }
          return refreshed
        }
        return false
      }
    },
    
    async refreshAccessToken() {
      if (!this.refreshToken) {
        console.error('刷新token失败: 没有可用的刷新令牌')
        this.clearUserData()
        return false
      }
      
      console.log('尝试刷新访问令牌...')
      
      try {
        const response = await axios.post(`${API_URL}/api/token/refresh`, {
          refresh_token: this.refreshToken
        })
        
        if (response.data.success) {
          // 更新access token
          this.accessToken = response.data.data.access_token
          // 同时更新两个key
          localStorage.setItem('accessToken', this.accessToken)
          localStorage.setItem('token', this.accessToken)
          this.updateActivityTime()
          console.log('访问令牌刷新成功')
          return true
        }
        
        console.warn('服务器返回成功但缺少token数据')
        return false
      } catch (error) {
        console.error('刷新访问令牌失败:', error.response?.data?.message || error.message)
        
        // 如果是401错误，可能是refresh token已过期或无效
        if (error.response?.status === 401) {
          console.warn('刷新令牌已过期或无效，清除用户数据')
          this.clearUserData()
        }
        return false
      }
    }
  }
})