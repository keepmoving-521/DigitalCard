<script setup lang="ts">
import { useRouter } from 'vue-router'
import { authState, logout } from '../auth'

const router = useRouter()
const hasPermission = (permission: string) =>
  authState.user?.permissions.includes(permission) ?? false

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
        <RouterLink v-if="authState.user?.role === 'platform_admin'" class="nav-item" to="/platform/companies">
          企业管理
        </RouterLink>
        <RouterLink v-if="authState.user?.role === 'platform_admin'" class="nav-item" to="/admin/accounts">
          账户管理
        </RouterLink>
        <RouterLink v-if="hasPermission('company.read')" class="nav-item" to="/company/settings">
          企业设置
        </RouterLink>
        <RouterLink v-if="hasPermission('department.read')" class="nav-item" to="/company/departments">
          部门管理
        </RouterLink>
        <RouterLink v-if="hasPermission('role.read')" class="nav-item" to="/company/roles">
          角色权限
        </RouterLink>
        <RouterLink v-if="hasPermission('audit.read')" class="nav-item" to="/company/audits">
          变更审计
        </RouterLink>
        <RouterLink class="nav-item" to="/change-password">修改密码</RouterLink>
      </nav>
      <div class="sidebar-user">
        <span class="avatar">{{ authState.user?.display_name.slice(0, 1) }}</span>
        <div><b>{{ authState.user?.display_name }}</b><small>{{ authState.user?.email }}</small></div>
      </div>
      <button class="text-button" type="button" @click="signOut">安全退出</button>
      <span class="version">V0.3.0 · 企业与权限</span>
    </aside>
    <main class="page-content"><slot /></main>
  </div>
</template>
