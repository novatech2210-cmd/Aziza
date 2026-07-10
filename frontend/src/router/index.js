import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// Set VITE_DEV_SKIP_AUTH=true in .env to bypass login during development
const SKIP_AUTH = import.meta.env.VITE_DEV_SKIP_AUTH === 'true'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { guest: true },
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('../views/ChatView.vue'),
    meta: { requiresAuth: !SKIP_AUTH },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/AdminView.vue'),
    meta: { requiresAuth: !SKIP_AUTH, requiresAdmin: !SKIP_AUTH },
  },
  {
    path: '/personas',
    name: 'Personas',
    component: () => import('../views/PersonaDashboard.vue'),
    meta: { requiresAuth: !SKIP_AUTH, requiresAdmin: !SKIP_AUTH },
  },
  {
    path: '/usage',
    name: 'Usage',
    component: () => import('../views/UsageView.vue'),
    meta: { requiresAuth: !SKIP_AUTH },
  },
  {
    path: '/',
    redirect: () => {
      if (SKIP_AUTH) return '/admin'
      const auth = useAuthStore()
      return auth.isAdmin ? '/admin' : '/chat'
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  if (SKIP_AUTH) return next()

  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return next('/login')
  }
  if (to.meta.requiresAdmin && auth.user?.role !== 'admin') {
    return next('/chat')
  }
  if (to.meta.guest && auth.isAuthenticated) {
    return next(auth.isAdmin ? '/admin' : '/chat')
  }
  next()
})

export default router
