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
        <RouterLink v-if="hasPermission('employee.read')" class="nav-item" to="/company/employees">
          员工管理
        </RouterLink>
        <RouterLink v-if="hasPermission('card.template.manage')" class="nav-item" to="/company/card-template">
          名片模板
        </RouterLink>
        <RouterLink v-if="hasPermission('product.read')" class="nav-item" to="/company/products">
          产品中心
        </RouterLink>
        <RouterLink v-if="hasPermission('material.read')" class="nav-item" to="/company/materials">
          素材库
        </RouterLink>
        <RouterLink v-if="hasPermission('lead.read')" class="nav-item" to="/company/leads">客户线索</RouterLink>
        <RouterLink v-if="hasPermission('customer.read')" class="nav-item" to="/company/customers">客户与商机</RouterLink>
        <RouterLink v-if="hasPermission('notification.read')" class="nav-item" to="/notifications">站内通知</RouterLink>
        <RouterLink v-if="hasPermission('role.read')" class="nav-item" to="/company/roles">
          角色权限
        </RouterLink>
        <RouterLink v-if="hasPermission('audit.read')" class="nav-item" to="/company/audits">
          变更审计
        </RouterLink>
        <RouterLink class="nav-item" to="/change-password">修改密码</RouterLink>
        <RouterLink v-if="hasPermission('employee.self_update')" class="nav-item" to="/profile">我的资料</RouterLink>
        <RouterLink v-if="hasPermission('card.read')" class="nav-item" to="/my-card">我的名片</RouterLink>
      </nav>
      <div class="sidebar-user">
        <span class="avatar">{{ authState.user?.display_name.slice(0, 1) }}</span>
        <div><b>{{ authState.user?.display_name }}</b><small>{{ authState.user?.email }}</small></div>
      </div>
      <button class="text-button" type="button" @click="signOut">安全退出</button>
      <span class="version">V0.9.0 · 客户 CRM</span>
    </aside>
    <main class="page-content"><slot /></main>
  </div>
</template>
