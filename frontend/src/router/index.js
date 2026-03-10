import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import LobbyView from '../views/LobbyView.vue'
import RoomView from '../views/RoomView.vue'
import ProfileView from '../views/ProfileView.vue'
import AdminView from '../views/AdminView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/login'
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView
    },
    {
      path: '/lobby',
      name: 'lobby',
      component: LobbyView,
      meta: { requiresAuth: true }
    },
    {
      path: '/room/:roomId',
      name: 'room',
      component: RoomView,
      meta: { requiresAuth: true }
    },
    {
      path: '/profile',
      name: 'profile',
      component: ProfileView,
      meta: { requiresAuth: true }
    },
    {
      path: '/admin',
      name: 'admin',
      component: AdminView,
      meta: { requiresAuth: true, requiresAdmin: true }
    }
  ]
})

// 导航守卫
router.beforeEach((to, from, next) => {
  // 使用token检查是否已登录
  const isAuthenticated = localStorage.getItem('token')
  // 检查是否是管理员
  const userDataStr = localStorage.getItem('userData')
  const isAdmin = userDataStr ? JSON.parse(userDataStr)?.is_admin : false
  
  if (to.matched.some(record => record.meta.requiresAuth) && !isAuthenticated) {
    // 需要登录但未登录，重定向到登录页
    next('/login')
  } else if (to.matched.some(record => record.meta.requiresAdmin) && !isAdmin) {
    // 需要管理员权限但不是管理员，重定向到大厅
    next('/lobby')
  } else if ((to.path === '/login' || to.path === '/register') && isAuthenticated) {
    // 已登录用户尝试访问登录或注册页，根据角色重定向
    if (isAdmin) {
      next('/admin')
    } else {
      next('/lobby')
    }
  } else {
    next()
  }
})

export default router
