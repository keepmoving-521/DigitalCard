<script setup lang="ts">
import { useRouter } from 'vue-router'
import { authState, logout } from '../auth'

const router = useRouter()

async function signOut() {
  await logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <RouterLink class="brand" to="/dashboard">
        <span class="brand-mark">D</span><span>DigitalCard</span>
      </RouterLink>
      <nav aria-label="主导航">
        <RouterLink class="nav-item" to="/dashboard">工作台</RouterLink>
        <RouterLink v-if="authState.user?.role === 'admin'" class="nav-item" to="/admin/accounts">
          账户管理
        </RouterLink>
        <RouterLink class="nav-item" to="/change-password">修改密码</RouterLink>
      </nav>
      <div class="sidebar-user">
        <span class="avatar">{{ authState.user?.display_name.slice(0, 1) }}</span>
        <div><b>{{ authState.user?.display_name }}</b><small>{{ authState.user?.email }}</small></div>
      </div>
      <button class="text-button" type="button" @click="signOut">安全退出</button>
      <span class="version">V0.2.0 · 账户与安全</span>
    </aside>
    <main class="page-content"><slot /></main>
  </div>
</template>

