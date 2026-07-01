import { createRouter, createWebHistory } from 'vue-router'
import { authState, initializeAuth, logout, syncCurrentUser } from './auth'
import AccountsView from './views/AccountsView.vue'
import ChangePasswordView from './views/ChangePasswordView.vue'
import DashboardView from './views/DashboardView.vue'
import ForbiddenView from './views/ForbiddenView.vue'
import LoginView from './views/LoginView.vue'
import AuditsView from './views/AuditsView.vue'
import CompaniesView from './views/CompaniesView.vue'
import CompanySettingsView from './views/CompanySettingsView.vue'
import DepartmentsView from './views/DepartmentsView.vue'
import RolesView from './views/RolesView.vue'
import EmployeesView from './views/EmployeesView.vue'
import MyProfileView from './views/MyProfileView.vue'
import AcceptInviteView from './views/AcceptInviteView.vue'
import CardEditorView from './views/CardEditorView.vue'
import CardTemplateView from './views/CardTemplateView.vue'
import MaterialsView from './views/MaterialsView.vue'
import ProductsView from './views/ProductsView.vue'
import LeadsView from './views/LeadsView.vue'
import NotificationsView from './views/NotificationsView.vue'
import CustomersView from './views/CustomersView.vue'
import MonitoringView from './views/MonitoringView.vue'
import NotFoundView from './views/NotFoundView.vue'
import OnboardingView from './views/OnboardingView.vue'
import AnalyticsView from './views/AnalyticsView.vue'
import MarketingView from './views/MarketingView.vue'
import SaasOperationsView from './views/SaasOperationsView.vue'
import KnowledgeAiView from './views/KnowledgeAiView.vue'
import OpenPlatformView from './views/OpenPlatformView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: LoginView, meta: { guest: true } },
    { path: '/accept-invite', component: AcceptInviteView, meta: { guest: true } },
    { path: '/dashboard', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/analytics', component: AnalyticsView, meta: { requiresAuth: true, permission: 'analytics.read' } },
    { path: '/company/marketing', component: MarketingView, meta: { requiresAuth: true, permission: 'marketing.read' } },
    { path: '/platform/saas', component: SaasOperationsView, meta: { requiresAuth: true, platform: true } },
    { path: '/company/knowledge-ai', component: KnowledgeAiView, meta: { requiresAuth: true, permission: 'knowledge.manage' } },
    { path: '/company/open-platform', component: OpenPlatformView, meta: { requiresAuth: true, permission: 'open_platform.manage' } },
    { path: '/onboarding', component: OnboardingView, meta: { requiresAuth: true, permission: 'company.read' } },
    { path: '/company/monitoring', component: MonitoringView, meta: { requiresAuth: true, permission: 'audit.read' } },
    {
      path: '/admin/accounts',
      component: AccountsView,
      meta: { requiresAuth: true, platform: true },
    },
    {
      path: '/platform/companies',
      component: CompaniesView,
      meta: { requiresAuth: true, platform: true },
    },
    {
      path: '/company/settings',
      component: CompanySettingsView,
      meta: { requiresAuth: true, permission: 'company.read' },
    },
    {
      path: '/company/departments',
      component: DepartmentsView,
      meta: { requiresAuth: true, permission: 'department.read' },
    },
    {
      path: '/company/employees',
      component: EmployeesView,
      meta: { requiresAuth: true, permission: 'employee.read' },
    },
    {
      path: '/profile',
      component: MyProfileView,
      meta: { requiresAuth: true, permission: 'employee.self_update' },
    },
    {
      path: '/my-card',
      component: CardEditorView,
      meta: { requiresAuth: true, permission: 'card.read' },
    },
    {
      path: '/company/card-template',
      component: CardTemplateView,
      meta: { requiresAuth: true, permission: 'card.template.manage' },
    },
    {
      path: '/company/cards/:employeeId',
      component: CardEditorView,
      meta: { requiresAuth: true, permission: 'card.manage' },
    },
    {
      path: '/company/products',
      component: ProductsView,
      meta: { requiresAuth: true, permission: 'product.read' },
    },
    {
      path: '/company/materials',
      component: MaterialsView,
      meta: { requiresAuth: true, permission: 'material.read' },
    },
    {
      path: '/company/leads', component: LeadsView,
      meta: { requiresAuth: true, permission: 'lead.read' },
    },
    {
      path: '/notifications', component: NotificationsView,
      meta: { requiresAuth: true, permission: 'notification.read' },
    },
    {
      path: '/company/customers', component: CustomersView,
      meta: { requiresAuth: true, permission: 'customer.read' },
    },
    {
      path: '/company/roles',
      component: RolesView,
      meta: { requiresAuth: true, permission: 'role.read' },
    },
    {
      path: '/company/audits',
      component: AuditsView,
      meta: { requiresAuth: true, permission: 'audit.read' },
    },
    { path: '/change-password', component: ChangePasswordView, meta: { requiresAuth: true } },
    { path: '/forbidden', component: ForbiddenView, meta: { requiresAuth: true } },
    { path: '/:pathMatch(.*)*', component: NotFoundView, meta: { requiresAuth: true } },
  ],
})

router.beforeEach(async (to) => {
  await initializeAuth()
  if (authState.user) {
    try {
      await syncCurrentUser()
    } catch {
      await logout()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  if (to.meta.requiresAuth && !authState.user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && authState.user) return '/dashboard'
  if (authState.user?.must_change_password && to.path !== '/change-password') {
    return '/change-password'
  }
  if (to.meta.platform && authState.user?.role !== 'platform_admin') return '/forbidden'
  if (
    typeof to.meta.permission === 'string' &&
    !authState.user?.permissions.includes(to.meta.permission)
  ) {
    return '/forbidden'
  }
  return true
})

export default router
