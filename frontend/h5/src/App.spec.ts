import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import App from './App.vue'

describe('H5 App', () => {
  it('renders the mobile foundation page', () => {
    const wrapper = mount(App)
    expect(wrapper.get('h1').text()).toContain('每一次连接')
    expect(wrapper.text()).toContain('FOUNDATION READY')
  })
})

