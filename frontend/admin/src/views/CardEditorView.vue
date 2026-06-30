<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError, apiRequest } from '../auth'
import type {
  CardPreview as Preview,
  CardStatus,
  CardTemplate,
  DigitalCard,
  SocialLink,
} from '../card'
import AppShell from '../components/AppShell.vue'
import CardPreview from '../components/CardPreview.vue'

interface Analytics { total_views: number; total_actions: number; by_event: Record<string, number>; by_source: Record<string, number> }
const route = useRoute()
const employeeId = computed(() => String(route.params.employeeId ?? ''))
const isOwn = computed(() => !employeeId.value)
const basePath = computed(() => isOwn.value ? '/tenant/cards/me' : `/tenant/cards/${employeeId.value}`)
const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const publicBase = import.meta.env.VITE_PUBLIC_CARD_BASE_URL ?? 'http://localhost:5174/card'
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const message = ref('')
const device = ref<'desktop' | 'mobile'>('mobile')
const status = ref<CardStatus>('draft')
const dirty = ref(false)
const cardId = ref('')
const template = ref<CardTemplate | null>(null)
const basePreview = ref<Record<string, unknown>>({})
const draftKeys = ref(new Set<string>())
const analytics = ref<Analytics>({ total_views: 0, total_actions: 0, by_event: {}, by_source: {} })
const publicOptions = [
  { code: 'headline', name: '职位/标语' }, { code: 'avatar_url', name: '头像' },
  { code: 'bio', name: '个人简介' }, { code: 'phone', name: '电话' },
  { code: 'email', name: '邮箱' }, { code: 'wechat', name: '微信' },
  { code: 'website', name: '网站' }, { code: 'socials', name: '社交账号' },
]
const form = reactive({
  display_name: '', headline: '', avatar_url: '', bio: '', phone: '', email: '',
  wechat: '', website: '', theme_color: '', logo_url: '', module_order: [] as string[],
  socials: [] as SocialLink[], visible_fields: [] as string[],
})
const shareUrl = computed(() => cardId.value ? `${publicBase}/${cardId.value}?source=employee` : '')
const qrUrl = computed(() => cardId.value ? `${apiBase}/public/cards/${cardId.value}/qr.svg?source=employee_qr` : '')
const localPreview = computed<Record<string, unknown>>(() => {
  const result: Record<string, unknown> = {
    ...basePreview.value, ...form, avatar_url: form.avatar_url || null,
    logo_url: form.logo_url || null,
    socials: form.socials.filter((item) => item.platform && item.url),
  }
  for (const field of publicOptions.map((item) => item.code)) {
    if (!form.visible_fields.includes(field)) delete result[field]
  }
  return result
})
const isLocked = (field: string) =>
  Boolean(template.value?.locked_fields.includes(field)) ||
  (isOwn.value && !template.value?.employee_editable_fields.includes(field))

function applyCard(card: DigitalCard, preview: Preview) {
  status.value = card.status
  dirty.value = card.has_unpublished_changes
  cardId.value = card.id
  basePreview.value = preview.data
  const data = card.draft_data
  draftKeys.value = new Set(Object.keys(data))
  Object.assign(form, {
    display_name: String(data.display_name ?? ''), headline: String(data.headline ?? ''),
    avatar_url: String(data.avatar_url ?? ''), bio: String(data.bio ?? ''),
    phone: String(data.phone ?? ''), email: String(data.email ?? ''),
    wechat: String(data.wechat ?? ''), website: String(data.website ?? ''),
    theme_color: String(data.theme_color ?? preview.data.theme_color ?? ''),
    logo_url: String(data.logo_url ?? preview.data.logo_url ?? ''),
    module_order: [...((data.module_order ?? preview.data.module_order ?? []) as string[])],
    socials: [...((data.socials ?? []) as SocialLink[])],
    visible_fields: [...((data.visible_fields ?? publicOptions.map((item) => item.code)) as string[])],
  })
}
async function load() {
  loading.value = true
  try {
    const [card, preview, templateValue, metricValue] = await Promise.all([
      apiRequest<DigitalCard>(basePath.value), apiRequest<Preview>(`${basePath.value}/preview`),
      apiRequest<CardTemplate>('/tenant/card-template'),
      apiRequest<Analytics>(`${basePath.value}/analytics`),
    ])
    template.value = templateValue
    analytics.value = metricValue
    applyCard(card, preview)
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '名片加载失败'
  } finally { loading.value = false }
}
function payload() {
  const values: Record<string, unknown> = {}
  const personalization = new Set(['theme_color', 'logo_url', 'module_order'])
  for (const [key, value] of Object.entries(form)) {
    if (isLocked(key)) continue
    if (
      personalization.has(key) && !draftKeys.value.has(key) &&
      JSON.stringify(value) === JSON.stringify(basePreview.value[key] ?? '')
    ) continue
    values[key] = key === 'socials'
      ? form.socials.filter((item) => item.platform && item.url)
      : value === '' ? null : value
  }
  return values
}
async function save(showMessage = true) {
  saving.value = true
  errorMessage.value = ''
  try {
    const card = await apiRequest<DigitalCard>(basePath.value, {
      method: 'PATCH', body: JSON.stringify(payload()),
    })
    dirty.value = card.has_unpublished_changes
    if (showMessage) message.value = '草稿已保存，线上名片未改变'
    return true
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '草稿保存失败'
    return false
  } finally { saving.value = false }
}
async function publish() {
  if (!await save(false)) return
  try {
    const card = await apiRequest<DigitalCard>(`${basePath.value}/publish`, { method: 'POST' })
    status.value = card.status
    dirty.value = false
    message.value = '名片已发布'
    await load()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '发布失败' }
}
async function offline() {
  try {
    const card = await apiRequest<DigitalCard>(`${basePath.value}/offline`, { method: 'POST' })
    status.value = card.status
    message.value = '名片已下线'
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '下线失败' }
}
async function copyShare() {
  await window.navigator.clipboard.writeText(shareUrl.value)
  message.value = '公开名片链接已复制'
}
function addSocial() {
  if (form.socials.length < 20) form.socials.push({ platform: '', url: '' })
}
onMounted(load)
</script>

<template>
  <AppShell>
    <header class="page-header compact">
      <div><p class="eyebrow">DIGITAL CARD</p><h1>{{ isOwn ? '我的数字名片' : '员工数字名片' }}</h1><p>草稿保存后不会影响线上内容，发布时才会生成新的公开快照。</p></div>
      <div class="card-status-actions"><span class="pill" :class="{ inactive: status !== 'published' }">{{ status === 'draft' ? '草稿' : status === 'published' ? '已发布' : '已下线' }}</span><span v-if="dirty" class="draft-badge">有未发布修改</span></div>
    </header>
    <div v-if="message" class="notice success">{{ message }}</div>
    <div v-if="errorMessage" class="notice error">{{ errorMessage }}</div>
    <div v-if="loading" class="panel empty-state">正在加载名片…</div>
    <div v-else class="card-editor-layout">
      <form class="panel form-panel card-form" @submit.prevent="save()">
        <label><span>展示姓名</span><input v-model.trim="form.display_name" :disabled="isLocked('display_name')" required /></label>
        <label><span>职位 / 个人标语</span><input v-model.trim="form.headline" :disabled="isLocked('headline')" /></label>
        <label><span>头像地址</span><input v-model.trim="form.avatar_url" :disabled="isLocked('avatar_url')" type="url" /></label>
        <label><span>个人简介</span><textarea v-model.trim="form.bio" :disabled="isLocked('bio')" rows="4" /></label>
        <div class="form-columns">
          <label><span>电话</span><input v-model.trim="form.phone" :disabled="isLocked('phone')" /></label>
          <label><span>邮箱</span><input v-model.trim="form.email" :disabled="isLocked('email')" type="email" /></label>
          <label><span>微信</span><input v-model.trim="form.wechat" :disabled="isLocked('wechat')" /></label>
          <label><span>个人网站</span><input v-model.trim="form.website" :disabled="isLocked('website')" type="url" /></label>
        </div>
        <fieldset v-if="!isLocked('socials')">
          <legend>社交账号</legend>
          <div v-for="(social, index) in form.socials" :key="index" class="social-row"><input v-model.trim="social.platform" placeholder="平台，如 LinkedIn" /><input v-model.trim="social.url" type="url" placeholder="https://" /><button type="button" class="link-button danger" @click="form.socials.splice(index, 1)">移除</button></div>
          <button type="button" class="secondary-button" @click="addSocial">添加社交账号</button>
        </fieldset>
        <fieldset class="check-grid">
          <legend>公开展示内容</legend>
          <label v-for="field in publicOptions" :key="field.code"><input v-model="form.visible_fields" type="checkbox" :value="field.code" />{{ field.name }}</label>
        </fieldset>
        <details><summary>个性化样式</summary><label><span>主题色</span><div class="color-field"><input v-model="form.theme_color" :disabled="isLocked('theme_color')" type="color" /><input v-model.trim="form.theme_color" :disabled="isLocked('theme_color')" /></div></label><label><span>Logo 地址</span><input v-model.trim="form.logo_url" :disabled="isLocked('logo_url')" type="url" /></label></details>
        <div class="form-actions"><button class="secondary-button" :disabled="saving">保存草稿</button><button class="primary-button" type="button" @click="publish">发布名片</button><button v-if="status === 'published'" class="link-button danger" type="button" @click="offline">下线</button></div>
      </form>
      <aside class="preview-panel">
        <div class="preview-toolbar"><p class="eyebrow">LIVE PREVIEW</p><div><button type="button" :class="{ active: device === 'desktop' }" @click="device = 'desktop'">桌面</button><button type="button" :class="{ active: device === 'mobile' }" @click="device = 'mobile'">手机</button></div></div>
        <CardPreview :data="localPreview" :device="device" />
        <section v-if="status === 'published'" class="card-share-tools"><div><span>访问次数</span><b>{{ analytics.total_views }}</b></div><div><span>关键操作</span><b>{{ analytics.total_actions }}</b></div><img :src="qrUrl" alt="公开名片二维码" /><button class="primary-button" type="button" @click="copyShare">复制公开链接</button></section>
      </aside>
    </div>
  </AppShell>
</template>
