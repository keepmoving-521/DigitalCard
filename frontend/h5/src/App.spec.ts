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
    expect(wrapper.text()).toContain('AI READY')
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

  it('renders and submits a dynamic marketing campaign', async () => {
    window.history.pushState({}, '', '/campaign/summer-demo?source=poster')
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes('/submissions')
        ? { id: 'submission-1', duplicate: false, message: '报名成功' }
        : { id: 'campaign-1', name: '夏日体验营', description: '新品体验', state: 'open', remaining: 5, privacy_notice: '同意活动联系', success_message: '报名成功', fields: [{ key: 'name', label: '姓名', type: 'text', required: true, options: [] }, { key: 'contact', label: '联系方式', type: 'phone', required: true, options: [] }] }),
    }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.text()).toContain('夏日体验营')
    const inputs = wrapper.findAll('.campaign-page form input')
    await inputs[0].setValue('王客户')
    await inputs[1].setValue('13800000000')
    await wrapper.get('.privacy-consent input').setValue(true)
    await wrapper.get('.campaign-page form').trigger('submit')
    await flushPromises()
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes('/submissions'))
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ source: 'poster', privacy_agreed: true })
    expect(wrapper.text()).toContain('报名成功')
  })

  it('answers public AI questions with sources and an advisory notice', async () => {
    window.history.pushState({}, '', '/ai/company-a')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ interaction_id: 'ai-1', answer: '标准交付周期是七个工作日。', uncertain: false, citations: [{ source_id: 'source-1', title: '交付周期', excerpt: '标准交付周期是七个工作日。' }], handoff_url: '/card/card-1?source=ai', suggestion_notice: 'AI 内容仅供参考' }) })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(App)
    await wrapper.get('.campaign-page textarea').setValue('交付周期多久？')
    await wrapper.get('.campaign-page form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('七个工作日')
    expect(wrapper.text()).toContain('交付周期')
    expect(wrapper.text()).toContain('AI 内容仅供参考')
    expect(wrapper.get('a').text()).toContain('转人工')
  })
})
