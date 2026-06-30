<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, apiRequest } from '../auth'
const route = useRoute(); const router = useRouter(); const password = ref(''); const confirmPassword = ref(''); const errorMessage = ref(''); const saving = ref(false); const token = computed(() => String(route.query.token ?? ''))
async function accept() {
  errorMessage.value = ''
  if (!token.value) { errorMessage.value = '邀请链接缺少令牌'; return }
  if (password.value !== confirmPassword.value) { errorMessage.value = '两次输入的密码不一致'; return }
  saving.value = true
  try { await apiRequest('/auth/invitations/accept', { method: 'POST', body: JSON.stringify({ token: token.value, password: password.value }) }); await router.replace('/login?invited=1') }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '邀请激活失败' }
  finally { saving.value = false }
}
</script>
<template><main class="invite-page"><form class="panel invite-form" @submit.prevent="accept"><p class="eyebrow">WELCOME</p><h1>开通员工账户</h1><p class="form-help">设置登录密码后，即可使用邀请邮箱登录管理端。</p><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div><label><span>新密码</span><input v-model="password" type="password" minlength="12" autocomplete="new-password" required /></label><label><span>确认密码</span><input v-model="confirmPassword" type="password" minlength="12" autocomplete="new-password" required /></label><p class="password-rules">至少 12 位，并包含大小写字母、数字和特殊字符。</p><button class="primary-button wide" :disabled="saving">{{ saving ? '正在开通…' : '完成开通' }}</button></form></main></template>
