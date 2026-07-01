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
    expect(wrapper.get('h1').text()).toContain('走向下一步')
    expect(wrapper.text()).toContain('LEADS READY')
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

  it('requires privacy consent and submits a traceable inquiry', async () => {
    window.history.pushState({}, '', '/card/card-2?source=campaign')
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/leads')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ id: 'lead-1', duplicate: false, message: '咨询已提交' }) })
      if (url.endsWith('/products')) return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      if (url.includes('/events')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ recorded: true }) })
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ card_id: 'card-2', employee_id: 'employee-2', published_at: '2026-07-01', share_url: 'http://localhost/card/card-2', data: { company_name: '企业', display_name: '销售', module_order: [] } }) })
    })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(App)
    await flushPromises()
    await wrapper.get('.inquiry-entry button').trigger('click')
    await wrapper.get('.inquiry-dialog').trigger('submit')
    expect(wrapper.text()).toContain('请先阅读并同意隐私授权')
    const inputs = wrapper.findAll('.inquiry-dialog input')
    await inputs[0].setValue('客户甲')
    await inputs[1].setValue('13800002222')
    await wrapper.get('.privacy-check input').setValue(true)
    await wrapper.get('.inquiry-dialog').trigger('submit')
    await flushPromises()
    const leadCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/leads'))
    expect(JSON.parse(String(leadCall?.[1]?.body))).toMatchObject({ source: 'campaign', privacy_agreed: true })
    expect(wrapper.text()).toContain('咨询已提交')
  })
})
