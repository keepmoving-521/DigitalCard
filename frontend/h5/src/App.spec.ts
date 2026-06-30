import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

describe('H5 App', () => {
  afterEach(() => {
    window.history.pushState({}, '', '/')
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('renders the mobile foundation page', () => {
    const wrapper = mount(App)
    expect(wrapper.get('h1').text()).toContain('每一次连接')
    expect(wrapper.text()).toContain('SHARING READY')
  })

  it('renders a published card and share QR entry', async () => {
    window.history.pushState({}, '', '/card/card-1?source=wechat')
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/events')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ recorded: true }) })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          card_id: 'card-1', employee_id: 'employee-1', published_at: '2026-06-30',
          share_url: 'http://localhost:5174/card/card-1?source=wechat',
          data: {
            company_name: '示例企业', display_name: '张三', headline: '客户顾问',
            phone: '13800000000', email: 'zhang@example.com', theme_color: '#123456',
            module_order: ['profile', 'contact', 'social', 'bio'],
          },
        }),
      })
    })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('拨打电话')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/public/cards/card-1?source=wechat'),
    )
    await wrapper.get('button[aria-label="显示分享二维码"]').trigger('click')
    expect(wrapper.get('img[alt="名片分享二维码"]').attributes('src')).toContain(
      '/public/cards/card-1/qr.svg?source=qr',
    )
  })
})
