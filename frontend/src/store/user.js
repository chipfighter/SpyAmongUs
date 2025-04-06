import { reactive } from 'vue'
import router from '../router'
import websocketService from '../services/websocket'

// API基础URL常量
const API_BASE_URL = 'http://localhost:8000';

export const userStore = reactive({
  user: null,
  loggedIn: false,
  error: null,
  loading: false,

  /**
   * 登录用户
   * @param {string} username 用户名
   * @param {string} password 密码
   * @returns {Promise<Object>} 登录结果
   */
  async loginWithPassword(username, password) {
    this.error = null;
    this.loading = true;
    
    try {
      // 构建登录请求
      const loginUrl = `${API_BASE_URL}/api/login`;
      
      // 使用JSON格式发送请求
      const response = await fetch(loginUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          username, 
          password 
        }),
      });
      
      // 检查HTTP响应
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('登录接口不存在，请检查后端服务');
        } else if (response.status === 401) {
          throw new Error('用户名或密码错误');
        } else {
          throw new Error(`服务器错误 (${response.status})`);
        }
      }
      
      // 解析响应JSON
      const data = await response.json();
      
      // 处理API响应
      if (data && data.user) {
        // 登录成功
        this.user = {
          id: data.user.id,
          username: data.user.username,
          displayName: data.user.username
        };
        
        this.loggedIn = true;
        
        // 保存到本地存储
        this.saveToLocalStorage();
        
        // 连接WebSocket
        try {
          await websocketService.connect(this.user.id);
        } catch (wsError) {
          console.error('WebSocket连接失败:', wsError);
          // 继续处理，允许用户即使没有WebSocket也能登录
        }
        
        return this.user;
      } else {
        throw new Error('服务器返回的用户数据无效');
      }
    } catch (e) {
      this.error = e.message;
      return null;
    } finally {
      this.loading = false;
    }
  },

  /**
   * 注册新用户
   * @param {string} username 用户名
   * @param {string} password 密码
   * @returns {Promise<Object>} 注册结果
   */
  async register(username, password) {
    this.error = null;
    this.loading = true;
    
    try {
      // 构建注册请求
      const registerUrl = `${API_BASE_URL}/api/register`;
      
      // 使用JSON格式发送请求
      const response = await fetch(registerUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          username, 
          password 
        }),
      });
      
      // 检查HTTP响应
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('注册接口不存在，请检查后端服务');
        } else if (response.status === 409) {
          throw new Error('用户名已存在，请尝试其他用户名');
        } else {
          throw new Error(`服务器错误 (${response.status})`);
        }
      }
      
      // 解析响应JSON
      const data = await response.json();
      
      // 处理API响应
      if (data && data.user) {
        // 注册成功
        this.user = {
          id: data.user.id,
          username: data.user.username,
          displayName: data.user.username
        };
        
        this.loggedIn = true;
        
        // 保存到本地存储
        this.saveToLocalStorage();
        
        // 连接WebSocket
        try {
          await websocketService.connect(this.user.id);
        } catch (wsError) {
          console.error('WebSocket连接失败:', wsError);
          // 继续处理，允许用户即使没有WebSocket也能登录
        }
        
        return this.user;
      } else {
        throw new Error('服务器返回的用户数据无效');
      }
    } catch (e) {
      this.error = e.message;
      return null;
    } finally {
      this.loading = false;
    }
  },

  /**
   * 注销用户
   */
  logout() {
    // 断开WebSocket连接
    websocketService.disconnect();
    
    // 清除用户数据
    this.user = null;
    this.loggedIn = false;
    
    // 清除本地存储
    localStorage.removeItem('user');
    
    // 返回登录页
    router.push('/login');
  },

  /**
   * 将用户信息保存到localStorage
   */
  saveToLocalStorage() {
    if (this.user) {
      localStorage.setItem('user', JSON.stringify(this.user));
    }
  },

  /**
   * 从localStorage恢复用户会话
   * @returns {boolean} 是否恢复成功
   */
  restoreFromLocalStorage() {
    try {
      const userData = localStorage.getItem('user');
      if (userData) {
        const user = JSON.parse(userData);
        if (user && user.id) {
          this.user = user;
          this.loggedIn = true;
          
          // 尝试连接WebSocket
          websocketService.connect(user.id).catch(error => {
            console.error('恢复会话时WebSocket连接失败:', error);
          });
          
          return true;
        }
      }
      return false;
    } catch (e) {
      console.error('恢复会话失败:', e);
      localStorage.removeItem('user');
      return false;
    }
  }
});

// 尝试初始化恢复会话
try {
  userStore.restoreFromLocalStorage();
} catch (e) {
  console.error('自动恢复会话失败:', e);
} 