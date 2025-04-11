import { defineStore } from 'pinia'
import axios from 'axios'

const API_URL = 'http://localhost:8000'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    accessToken: null,
    refreshToken: null,
    loading: false,
    error: null,
    lastActivityTime: Date.now() // 添加用户最后活动时间
  }),
  
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    userAvatar: (state) => state.user?.avatar_url || '/default_avatar.jpg',
    // 检查会话是否过期 (25分钟无活动)
    isSessionExpired: (state) => {
      if (!state.lastActivityTime) return true
      const inactiveTime = Date.now() - state.lastActivityTime
      // 如果用户超过24分钟无活动，视为会话过期 (小于JWT的25分钟)
      return inactiveTime > 24 * 60 * 1000
    }
  },
  
  actions: {
    // 更新最后活动时间
    updateActivityTime() {
      this.lastActivityTime = Date.now()
      localStorage.setItem('lastActivityTime', this.lastActivityTime.toString())
    },
    
    // 初始化状态（从localStorage加载）
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
      }
    },
    
    // 保存用户数据到localStorage
    saveUserData() {
      if (this.accessToken) {
        localStorage.setItem('accessToken', this.accessToken)
        localStorage.setItem('refreshToken', this.refreshToken || '')
        localStorage.setItem('userData', JSON.stringify(this.user))
        localStorage.setItem('lastActivityTime', this.lastActivityTime.toString())
      }
    },
    
    // 设置请求头
    setAuthHeader() {
      if (this.accessToken) {
        axios.defaults.headers.common['Authorization'] = this.accessToken
      } else {
        delete axios.defaults.headers.common['Authorization']
      }
    },
    
    // 登录
    async login(username, password) {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.post(`${API_URL}/api/login`, { username, password })
        
        if (response.data.success) {
          const { data } = response.data
          this.user = data
          this.accessToken = data.access_token
          this.refreshToken = data.refresh_token
          this.updateActivityTime()
          this.saveUserData()
          this.setAuthHeader()
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
    
    // 注册
    async register(username, password) {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.post(`${API_URL}/api/register`, { username, password })
        
        if (response.data.success) {
          const { user_id, user_data } = response.data.data
          this.user = user_data
          this.accessToken = user_data.access_token
          this.refreshToken = user_data.refresh_token
          this.updateActivityTime()
          this.saveUserData()
          this.setAuthHeader()
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
    
    // 登出
    async logout() {
      this.loading = true
      this.error = null
      
      try {
        if (this.user?.id) {
          await axios.post(`${API_URL}/api/logout`, { user_id: this.user.id })
        }
      } catch (error) {
        console.error('登出时发生错误:', error)
      } finally {
        // 无论后端响应如何，都清除本地状态
        this.clearUserData()
        this.loading = false
      }
    },
    
    // 清除用户数据
    clearUserData() {
      this.user = null
      this.accessToken = null
      this.refreshToken = null
      this.lastActivityTime = null
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('userData')
      localStorage.removeItem('lastActivityTime')
      delete axios.defaults.headers.common['Authorization']
    },
    
    // 检查用户状态
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
          this.clearUserData()
        }
        return false
      }
    }
  }
})