<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, unknown>; device?: 'desktop' | 'mobile' }>()
const modules = computed(() => (props.data.module_order as string[] | undefined) ?? ['profile', 'contact', 'social', 'bio'])
const socials = computed(() => (props.data.socials as Array<{ platform: string; url: string }> | undefined) ?? [])
const value = (key: string) => String(props.data[key] ?? '')
</script>

<template>
  <div class="preview-stage" :class="device ?? 'mobile'">
    <article class="digital-card-preview" :style="{ '--card-theme': value('theme_color') || '#1c6a42' }">
      <header class="card-brand"><img v-if="value('logo_url')" :src="value('logo_url')" alt="企业 Logo" /><b>{{ value('company_name') || '企业名称' }}</b></header>
      <template v-for="module in modules" :key="module">
        <section v-if="module === 'profile'" class="card-profile"><img v-if="value('avatar_url')" :src="value('avatar_url')" alt="头像" /><span v-else class="preview-avatar">{{ value('display_name').slice(0, 1) || 'D' }}</span><div><h2>{{ value('display_name') || '姓名' }}</h2><p>{{ value('headline') || '职位或个人标语' }}</p></div></section>
        <section v-else-if="module === 'contact'" class="card-module"><h3>联系方式</h3><p v-if="value('phone')">电话 · {{ value('phone') }}</p><p v-if="value('email')">邮箱 · {{ value('email') }}</p><p v-if="value('wechat')">微信 · {{ value('wechat') }}</p><p v-if="value('website')">网站 · {{ value('website') }}</p><p v-if="!value('phone') && !value('email')" class="muted">发布前至少填写电话或邮箱</p></section>
        <section v-else-if="module === 'social' && socials.length" class="card-module"><h3>社交账号</h3><p v-for="social in socials" :key="`${social.platform}-${social.url}`">{{ social.platform }} · {{ social.url }}</p></section>
        <section v-else-if="module === 'bio' && value('bio')" class="card-module"><h3>关于我</h3><p>{{ value('bio') }}</p></section>
      </template>
    </article>
  </div>
</template>
