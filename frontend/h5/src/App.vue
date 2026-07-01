<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

interface PublicCard { card_id: string; employee_id: string; data: Record<string, unknown>; published_at: string; share_url: string }
interface ProductSummary { id: string; name: string; summary: string | null; cover_url: string | null }
interface ProductDetail extends ProductSummary { description: string | null; specifications: Record<string, string>; gallery_urls: string[]; video_url: string | null; attachment_urls: string[] }
const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const card = ref<PublicCard | null>(null); const loading = ref(true); const unavailable = ref(''); const showQr = ref(false); const toast = ref('')
const products = ref<ProductSummary[]>([]); const selectedProduct = ref<ProductDetail | null>(null)
const cardId = window.location.pathname.match(/^\/card\/([^/]+)\/?$/)?.[1] ?? ''
const source = (new URLSearchParams(window.location.search).get('source') ?? 'direct').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64) || 'direct'
const data = computed(() => card.value?.data ?? {}); const modules = computed(() => (data.value.module_order as string[] | undefined) ?? ['profile', 'contact', 'social', 'bio']); const socials = computed(() => (data.value.socials as Array<{ platform: string; url: string }> | undefined) ?? [])
const value = (key: string) => String(data.value[key] ?? '')
const assetUrl = (path: string | null) => !path ? '' : /^https?:\/\//.test(path) ? path : `${new URL(apiBase).origin}${path}`
function visitorId() { const key = 'digitalcard_visitor_id'; let id = localStorage.getItem(key); if (!id) { id = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`; localStorage.setItem(key, id) } return id }
async function track(event_type: string) { if (!card.value) return; try { await fetch(`${apiBase}/public/cards/${card.value.card_id}/events`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_type, visitor_id: visitorId(), source }), keepalive: true }) } catch { /* Analytics must never block customer actions. */ } }
function linkFor(channel: string) { if (!card.value) return ''; const url = new URL(card.value.share_url); url.searchParams.set('source', channel); return url.toString() }
async function copyText(text: string, message: string) { await navigator.clipboard.writeText(text); toast.value = message; window.setTimeout(() => { toast.value = '' }, 1800) }
async function copyShare() { await copyText(linkFor('copy'), '分享链接已复制'); void track('share_copy') }
async function nativeShare() { const link = linkFor('native'); if (navigator.share) { await navigator.share({ title: value('display_name'), text: value('headline'), url: link }) } else await copyText(link, '分享链接已复制'); void track('share_copy') }
async function copyWechat() { await copyText(value('wechat'), '微信号已复制'); void track('wechat_copy') }
function call() { void track('call'); window.location.href = `tel:${value('phone')}` }
function email() { void track('email'); window.location.href = `mailto:${value('email')}` }
function escapeVcard(text: string) { return text.replace(/\\/g, '\\\\').replace(/,/g, '\\,').replace(/;/g, '\\;').replace(/\n/g, '\\n') }
function saveContact() { const lines = ['BEGIN:VCARD', 'VERSION:3.0', `FN:${escapeVcard(value('display_name'))}`, `ORG:${escapeVcard(value('company_name'))}`]; if (value('headline')) lines.push(`TITLE:${escapeVcard(value('headline'))}`); if (value('phone')) lines.push(`TEL;TYPE=CELL:${value('phone')}`); if (value('email')) lines.push(`EMAIL:${value('email')}`); if (value('website')) lines.push(`URL:${value('website')}`); lines.push('END:VCARD'); const url = URL.createObjectURL(new Blob([lines.join('\r\n')], { type: 'text/vcard;charset=utf-8' })); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${value('display_name') || 'contact'}.vcf`; anchor.click(); URL.revokeObjectURL(url); void track('vcard_download') }
function openQr() { showQr.value = true; void track('qr_open') }
async function openProduct(id: string) { const response = await fetch(`${apiBase}/public/products/${id}`); if (response.ok) { selectedProduct.value = await response.json(); void track('product_open') } }
async function loadCard() { if (!cardId) { loading.value = false; return } try { const response = await fetch(`${apiBase}/public/cards/${encodeURIComponent(cardId)}?source=${encodeURIComponent(source)}`); const body = await response.json(); if (!response.ok) { const code = body.error?.code; unavailable.value = code === 'card_offline' ? '这张名片暂时下线了' : code === 'employee_inactive' ? '该员工名片已停止展示' : code === 'company_suspended' ? '该企业名片暂时不可访问' : '没有找到可公开访问的名片'; return } card.value = body; const productResponse = await fetch(`${apiBase}/public/cards/${encodeURIComponent(cardId)}/products`); if (productResponse.ok) products.value = await productResponse.json(); void track('view') } catch { unavailable.value = '网络开小差了，请稍后再试' } finally { loading.value = false } }
onMounted(loadCard)
</script>

<template>
  <main v-if="!cardId" class="landing"><section class="landing-hero"><span class="landing-logo">DC</span><span class="badge">V0.7.0</span><div><p>DIGITAL BUSINESS CARD</p><h1>连接之外，<br />让产品自己说话。</h1><span>通过专属名片展示企业、员工与推荐产品。</span></div></section><section class="landing-info"><p>PRODUCT READY</p><h2>名片与企业内容中心</h2><div><article>移动优先公开页</article><article>产品与案例展示</article><article>销售资料安全分享</article></div></section></main>
  <main v-else-if="loading" class="state-page"><span class="state-mark">DC</span><h1>正在打开名片</h1><p>请稍候，正在加载公开信息…</p></main>
  <main v-else-if="unavailable" class="state-page"><span class="state-mark">—</span><h1>{{ unavailable }}</h1><p>名片可能尚未发布、已下线，或所属企业暂时停用。</p></main>
  <main v-else-if="card" class="public-card" :style="{ '--theme': value('theme_color') || '#1c6a42' }">
    <header class="public-brand"><img v-if="value('logo_url')" :src="value('logo_url')" alt="企业 Logo" /><b>{{ value('company_name') }}</b><button type="button" aria-label="显示分享二维码" @click="openQr">▦</button></header>
    <template v-for="module in modules" :key="module">
      <section v-if="module === 'profile'" class="public-profile"><img v-if="value('avatar_url')" :src="value('avatar_url')" alt="头像" /><span v-else>{{ value('display_name').slice(0, 1) }}</span><p>HELLO, I AM</p><h1>{{ value('display_name') }}</h1><h2 v-if="value('headline')">{{ value('headline') }}</h2></section>
      <section v-else-if="module === 'contact'" class="action-grid"><button v-if="value('phone')" type="button" @click="call"><i>☎</i><span>拨打电话</span></button><button v-if="value('email')" type="button" @click="email"><i>✉</i><span>发送邮件</span></button><button v-if="value('wechat')" type="button" @click="copyWechat"><i>微</i><span>复制微信</span></button><button type="button" @click="saveContact"><i>＋</i><span>保存通讯录</span></button></section>
      <section v-else-if="module === 'bio' && value('bio')" class="content-module"><p class="section-label">ABOUT</p><h3>关于我</h3><p>{{ value('bio') }}</p></section>
      <section v-else-if="module === 'social' && socials.length" class="content-module"><p class="section-label">SOCIAL</p><h3>社交账号</h3><a v-for="social in socials" :key="social.url" :href="social.url" target="_blank" rel="noopener noreferrer">{{ social.platform }}<span>↗</span></a></section>
    </template>
    <section v-if="products.length" class="product-module"><p class="section-label">FEATURED PRODUCTS</p><h3>推荐产品</h3><button v-for="product in products" :key="product.id" type="button" class="product-card" @click="openProduct(product.id)"><img v-if="product.cover_url" :src="assetUrl(product.cover_url)" alt="" /><span><b>{{ product.name }}</b><small>{{ product.summary || '查看产品详情' }}</small></span><i>›</i></button></section>
    <section class="share-panel"><p class="section-label">SHARE</p><h3>把这张名片分享给更多人</h3><div><button type="button" @click="copyShare">复制链接</button><button type="button" @click="nativeShare">系统分享</button><button type="button" @click="openQr">二维码</button></div></section>
    <footer>DigitalCard · 安全展示已发布信息</footer>
    <div v-if="showQr" class="qr-backdrop" @click.self="showQr = false"><section class="qr-dialog"><button type="button" aria-label="关闭二维码" @click="showQr = false">×</button><p class="section-label">SCAN TO CONNECT</p><h3>扫码打开名片</h3><img :src="`${apiBase}/public/cards/${card.card_id}/qr.svg?source=qr`" alt="名片分享二维码" /><small>二维码包含当前名片地址和来源参数</small></section></div>
    <div v-if="selectedProduct" class="product-backdrop" @click.self="selectedProduct = null"><article class="product-detail"><button class="product-close" type="button" @click="selectedProduct = null">×</button><img v-if="selectedProduct.cover_url" class="product-cover" :src="assetUrl(selectedProduct.cover_url)" alt="" /><p class="section-label">PRODUCT</p><h2>{{ selectedProduct.name }}</h2><p>{{ selectedProduct.description || selectedProduct.summary }}</p><div v-if="selectedProduct.gallery_urls.length" class="product-gallery"><img v-for="url in selectedProduct.gallery_urls" :key="url" :src="assetUrl(url)" alt="产品图片" /></div><video v-if="selectedProduct.video_url" controls :src="assetUrl(selectedProduct.video_url)" /><dl v-if="Object.keys(selectedProduct.specifications).length"><template v-for="(item, key) in selectedProduct.specifications" :key="key"><dt>{{ key }}</dt><dd>{{ item }}</dd></template></dl><a v-for="(url, index) in selectedProduct.attachment_urls" :key="url" :href="assetUrl(url)" target="_blank" rel="noopener">查看附件 {{ index + 1 }}</a></article></div>
    <div v-if="toast" class="toast">{{ toast }}</div>
  </main>
</template>
