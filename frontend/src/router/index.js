import { createRouter, createWebHistory } from 'vue-router'
import { userStore } from '../store/user'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue')
  },
  {
    path: '/lobby',
    name: 'Lobby',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/room/:id',
    name: 'Room',
    component: () => import('../views/Room.vue'),
    props: true,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局路由守卫，检查登录状态
router.beforeEach((to, from, next) => {
  // 检查是否登录
  const isLoggedIn = userStore.loggedIn && userStore.user && userStore.user.id;
  
  // 如果需要登录但未登录，重定向到登录页
  if (to.meta.requiresAuth && !isLoggedIn) {
    next('/login');
  } else {
    // 如果已登录且尝试访问登录或注册页，则重定向到大厅
    if (isLoggedIn && (to.path === '/login' || to.path === '/register')) {
      next('/lobby');
    } else {
      next();
    }
  }
})

export default router
