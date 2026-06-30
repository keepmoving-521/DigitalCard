import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it } from 'vitest'
import { authState } from './auth'
import AppShell from './components/AppShell.vue'
import ForbiddenView from './views/ForbiddenView.vue'
import LoginView from './views/LoginView.vue'

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', component: LoginView },
      { path: '/forbidden', component: ForbiddenView },
      { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/change-password', component: { template: '<div>Password</div>' } },
      { path: '/company/settings', component: { template: '<div>Company</div>' } },
      { path: '/company/departments', component: { template: '<div>Departments</div>' } },
      { path: '/company/employees', component: { template: '<div>Employees</div>' } },
      { path: '/profile', component: { template: '<div>Profile</div>' } },
      { path: '/company/roles', component: { template: '<div>Roles</div>' } },
      { path: '/company/audits', component: { template: '<div>Audits</div>' } },
      { path: '/platform/companies', component: { template: '<div>Companies</div>' } },
      { path: '/admin/accounts', component: { template: '<div>Accounts</div>' } },
    ],
  })
}

describe('Account foundation views', () => {
  afterEach(() => {
    authState.user = null
    authState.accessToken = null
    authState.initialized = false
  })
  it('renders the login form', async () => {
    const router = testRouter()
    await router.push('/login')
    await router.isReady()
    const wrapper = mount(LoginView, { global: { plugins: [router] } })
    expect(wrapper.get('h2').text()).toBe('登录管理端')
    expect(wrapper.get('input[type="email"]').attributes('autocomplete')).toBe('username')
    expect(wrapper.get('input[type="password"]').attributes('autocomplete')).toBe(
      'current-password',
    )
  })

  it('renders the permission denied page', async () => {
    const router = testRouter()
    await router.push('/forbidden')
    await router.isReady()
    const wrapper = mount(ForbiddenView, {
      global: {
        plugins: [router],
        stubs: { AppShell: { template: '<main><slot /></main>' } },
      },
    })
    expect(wrapper.text()).toContain('你没有访问此页面的权限')
  })

  it('only renders navigation entries granted to the tenant role', async () => {
    authState.user = {
      id: 'user-1', email: 'content@example.com', display_name: '内容管理员',
      role: 'content_admin', company_id: 'company-1', department_id: null,
      permissions: ['company.read', 'department.read', 'employee.read', 'content.manage'], is_active: true,
      must_change_password: false, last_login_at: null, created_at: '', updated_at: '',
    }
    const router = testRouter()
    await router.push('/dashboard')
    await router.isReady()
    const wrapper = mount(AppShell, {
      slots: { default: '<div>Content</div>' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('a[href="/company/settings"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/company/departments"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/company/employees"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/company/roles"]').exists()).toBe(false)
    expect(wrapper.find('a[href="/admin/accounts"]').exists()).toBe(false)
  })
})
