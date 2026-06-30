import { createRouter, createWebHistory } from 'vue-router'
import { authState, initializeAuth } from './auth'
import AccountsView from './views/AccountsView.vue'
import ChangePasswordView from './views/ChangePasswordView.vue'
import DashboardView from './views/DashboardView.vue'
import ForbiddenView from './views/ForbiddenView.vue'
import LoginView from './views/LoginView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: LoginView, meta: { guest: true } },
    { path: '/dashboard', component: DashboardView, meta: { requiresAuth: true } },
    {
      path: '/admin/accounts',
      component: AccountsView,
      meta: { requiresAuth: true, role: 'admin' },
    },
    { path: '/change-password', component: ChangePasswordView, meta: { requiresAuth: true } },
    { path: '/forbidden', component: ForbiddenView, meta: { requiresAuth: true } },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  await initializeAuth()
  if (to.meta.requiresAuth && !authState.user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && authState.user) return '/dashboard'
  if (authState.user?.must_change_password && to.path !== '/change-password') {
    return '/change-password'
  }
  if (to.meta.role && authState.user?.role !== to.meta.role) return '/forbidden'
  return true
})

export default router

