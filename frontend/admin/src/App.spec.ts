import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import App from './App.vue'

describe('Admin App', () => {
  it('renders the engineering foundation overview', () => {
    const wrapper = mount(App)
    expect(wrapper.get('h1').text()).toBe('DigitalCard 管理端')
    expect(wrapper.text()).toContain('V0.2.0 · 账户与登录')
  })
})

