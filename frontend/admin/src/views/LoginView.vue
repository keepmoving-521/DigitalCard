<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, login } from '../auth'

const route = useRoute()
const router = useRouter()
const email = ref('')
const password = ref('')
const errorMessage = ref('')
const submitting = ref(false)

const messages: Record<string, string> = {
  invalid_credentials: '邮箱或密码不正确',
  account_locked: '登录失败次数过多，请稍后再试',
  account_disabled: '账户已停用，请联系管理员',
  company_suspended: '企业空间已暂停，请联系平台运营方',
}

async function submit() {
  errorMessage.value = ''
  submitting.value = true
  try {
    const user = await login(email.value, password.value)
    if (user.must_change_password) {
      await router.replace('/change-password')
      return
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    await router.replace(redirect)
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError ? (messages[error.code] ?? error.message) : '暂时无法登录，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <RouterLink class="brand brand-light" to="/">
        <span class="brand-mark">D</span><span>DigitalCard</span>
      </RouterLink>
      <div>
        <p class="eyebrow light">SECURE CONNECTION</p>
        <h1>让每一次客户连接，<br />都有迹可循。</h1>
        <p>统一管理企业名片、内容与客户关系。</p>
      </div>
      <span class="story-version">V0.3.0 · Tenant Foundation</span>
    </section>
    <section class="login-panel">
      <form class="login-form" @submit.prevent="submit">
        <p class="eyebrow">WELCOME BACK</p>
        <h2>登录管理端</h2>
        <p class="form-help">使用管理员分配的企业账户继续。</p>
        <div v-if="route.query.passwordChanged" class="notice success">密码已更新，请重新登录。</div>
        <div v-if="errorMessage" class="notice error" role="alert">{{ errorMessage }}</div>
        <label>
          <span>邮箱</span>
          <input v-model.trim="email" type="email" autocomplete="username" required placeholder="name@company.com" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" required placeholder="输入登录密码" />
        </label>
        <button class="primary-button wide" type="submit" :disabled="submitting">
          {{ submitting ? '正在验证…' : '安全登录' }}
        </button>
        <small class="security-note">连续登录失败将临时锁定账户。请勿与他人共享密码。</small>
      </form>
    </section>
  </main>
</template>
