import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { authState } from './auth'
import AppShell from './components/AppShell.vue'
import ForbiddenView from './views/ForbiddenView.vue'
import LoginView from './views/LoginView.vue'
import CardPreview from './components/CardPreview.vue'
import ProductsView from './views/ProductsView.vue'

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', component: LoginView },
      { path: '/forbidden', component: ForbiddenView },
      { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/onboarding', component: { template: '<div>Onboarding</div>' } },
      { path: '/company/monitoring', component: { template: '<div>Monitoring</div>' } },
      { path: '/change-password', component: { template: '<div>Password</div>' } },
      { path: '/company/settings', component: { template: '<div>Company</div>' } },
      { path: '/company/departments', component: { template: '<div>Departments</div>' } },
      { path: '/company/employees', component: { template: '<div>Employees</div>' } },
      { path: '/company/card-template', component: { template: '<div>Template</div>' } },
      { path: '/company/products', component: { template: '<div>Products</div>' } },
      { path: '/company/materials', component: { template: '<div>Materials</div>' } },
      { path: '/company/leads', component: { template: '<div>Leads</div>' } },
      { path: '/company/customers', component: { template: '<div>Customers</div>' } },
      { path: '/analytics', component: { template: '<div>Analytics</div>' } },
      { path: '/notifications', component: { template: '<div>Notifications</div>' } },
      { path: '/company/cards/:employeeId', component: { template: '<div>Card</div>' } },
      { path: '/my-card', component: { template: '<div>My card</div>' } },
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
    vi.unstubAllGlobals()
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

  it('renders a live digital card preview', () => {
    const wrapper = mount(CardPreview, {
      props: {
        device: 'mobile',
        data: {
          company_name: '示例企业', display_name: '张三', headline: '客户顾问',
          phone: '13800000000', theme_color: '#123456',
          module_order: ['profile', 'contact', 'social', 'bio'], socials: [],
        },
      },
    })
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('13800000000')
    expect(wrapper.classes()).not.toContain('desktop')
  })

  it('lets an employee browse products without requesting material permission', async () => {
    authState.user = {
      id: 'user-2', email: 'employee@example.com', display_name: '普通员工',
      role: 'employee', company_id: 'company-1', department_id: null,
      permissions: ['product.read'], is_active: true, must_change_password: false,
      last_login_at: null, created_at: '', updated_at: '',
    }
    authState.accessToken = 'test-token'
    const fetchMock = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
      url.includes('product-categories') ? [] : { items: [], total: 0, offset: 0, limit: 100 },
    ), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(ProductsView, {
      global: { stubs: { AppShell: { template: '<main><slot /></main>' } } },
    })
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/tenant/materials'))).toBe(false)
    expect(wrapper.text()).toContain('浏览企业已维护的产品')
    expect(wrapper.text()).not.toContain('新增产品')
  })
})
