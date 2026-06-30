<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, apiRequest, logout } from '../auth'
import AppShell from '../components/AppShell.vue'

const router = useRouter()
const currentPassword = ref('')
const newPassword = ref('')
const confirmation = ref('')
const errorMessage = ref('')
const submitting = ref(false)

async function submit() {
  errorMessage.value = ''
  if (newPassword.value !== confirmation.value) {
    errorMessage.value = '两次输入的新密码不一致'
    return
  }
  submitting.value = true
  try {
    await apiRequest<void>('/auth/me/password', {
      method: 'PUT',
      body: JSON.stringify({ current_password: currentPassword.value, new_password: newPassword.value }),
    })
    await logout()
    await router.replace({ path: '/login', query: { passwordChanged: '1' } })
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '密码修改失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppShell>
    <header class="page-header compact"><div><p class="eyebrow">SECURITY</p><h1>修改密码</h1><p>修改成功后，所有设备上的旧会话都会立即失效。</p></div></header>
    <form class="panel form-panel" @submit.prevent="submit">
      <div v-if="errorMessage" class="notice error" role="alert">{{ errorMessage }}</div>
      <label><span>当前密码</span><input v-model="currentPassword" type="password" autocomplete="current-password" required /></label>
      <label><span>新密码</span><input v-model="newPassword" type="password" autocomplete="new-password" minlength="12" required /></label>
      <label><span>确认新密码</span><input v-model="confirmation" type="password" autocomplete="new-password" minlength="12" required /></label>
      <p class="password-rules">至少 12 位，并同时包含大写字母、小写字母、数字和特殊字符；不能包含邮箱名称。</p>
      <button class="primary-button" type="submit" :disabled="submitting">{{ submitting ? '正在更新…' : '更新密码' }}</button>
    </form>
  </AppShell>
</template>

