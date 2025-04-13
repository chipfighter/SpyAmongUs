import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'
import App from './App.vue'
import router from './router'
import { API_URL } from '@/config'

// --------------------------------------------------
// API分类和配置
// --------------------------------------------------

// 不需要认证的公开API路径
const PUBLIC_APIS = [
  '/api/login',
  '/api/register',
  '/api/token/refresh', 
  '/api/refresh-token',
  '/api/token/rotate',
  '/'
]

// 需要特殊处理的API（不应用全局处理逻辑）
// 这些API应该在各自的方法中直接处理认证和错误
const SPECIAL_APIS = [
  '/api/logout'
]

// --------------------------------------------------
// 请求拦截器：处理认证头
// --------------------------------------------------

axios.interceptors.request.use(config => {
  // 提取相对路径（去掉API_URL前缀）
  const url = config.url;
  const relativePath = url.replace(API_URL, '');
  
  // 开发环境日志
  console.log(`发送请求: ${config.method?.toUpperCase() || 'GET'} ${url}`);
  console.log(`相对路径: ${relativePath}`);
  
  // OPTIONS预检请求不添加认证头
  if (config.method?.toLowerCase() === 'options') {
    console.log('OPTIONS预检请求，不添加认证头');
    return config;
  }
  
  // 检查是否为公开API或特殊API
  const isPublicApi = PUBLIC_APIS.some(path => relativePath === path || relativePath.startsWith(`${path}/`));
  const isSpecialApi = SPECIAL_APIS.some(path => relativePath === path || relativePath.startsWith(`${path}/`));
  
  console.log(`请求类型: ${isPublicApi ? '公开API' : isSpecialApi ? '特殊API' : '需要认证的API'}`);
  
  // 特殊API不在拦截器中处理认证（在各自方法中直接处理）
  if (isSpecialApi) {
    console.log('特殊API，跳过全局认证处理:', url);
    return config;
  }
  
  // 公开API不需要认证
  if (isPublicApi) {
    console.log('公开API，不添加认证头:', url);
    return config;
  }
  
  // 为受保护API添加认证头
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
    console.log('添加认证头: Bearer ' + token.substring(0, 10) + '...');
  } else {
    console.warn('警告: 访问受保护API但未找到token');
  }
  
  return config;
}, error => {
  return Promise.reject(error);
})

// --------------------------------------------------
// 响应拦截器：处理认证错误
// --------------------------------------------------

axios.interceptors.response.use(
  response => {
    console.log(`请求成功: ${response.config.url} (${response.status})`)
    return response
  },
  error => {
    console.error(`请求失败: ${error.config?.url} (${error.response?.status || '未知状态码'})`)
    console.error(`错误信息: ${error.response?.data?.message || error.message}`)
    
    // 处理401错误（未认证）
    if (error.response?.status === 401) {
      // 特殊API的错误不在全局拦截器中处理
      const isSpecialApi = SPECIAL_APIS.some(path => error.config.url === path)
      if (isSpecialApi) {
        console.log('特殊API的401错误，跳过全局处理:', error.config.url)
        return Promise.reject(error)
      }
      
      console.warn('认证失败，清除用户信息并跳转到登录页')
      
      // 清除所有用户相关存储
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('userData')
      localStorage.removeItem('lastActivityTime')
      
      // 重定向到登录页
      router.push('/login')
    }
    
    return Promise.reject(error)
  }
)

// --------------------------------------------------
// 创建Vue应用
// --------------------------------------------------

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.mount('#app')
