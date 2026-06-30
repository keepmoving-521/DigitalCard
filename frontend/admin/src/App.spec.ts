import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
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
    ],
  })
}

describe('Account foundation views', () => {
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
})
