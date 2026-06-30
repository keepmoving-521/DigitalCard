<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ApiError, apiRequest, authState, type User } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { Company } from '../organization'

const users = ref<User[]>([])
const companies = ref<Company[]>([])
const loading = ref(true)
const errorMessage = ref('')
const showCreate = ref(false)
const resetTarget = ref<User | null>(null)
const resetPassword = ref('')
const form = reactive({
  email: '', display_name: '', password: '', role: 'employee', company_id: '',
})
const roleNames: Record<string, string> = {
  platform_admin: '平台管理员', company_admin: '企业管理员', content_admin: '内容管理员',
  sales: '销售', employee: '普通员工',
}
const companyName = (companyId: string | null) =>
  companies.value.find((company) => company.id === companyId)?.name ?? '平台'

async function loadUsers() {
  loading.value = true
  try { users.value = await apiRequest<User[]>('/admin/users') }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '账户加载失败' }
  finally { loading.value = false }
}

async function loadCompanies() {
  companies.value = await apiRequest<Company[]>('/platform/companies')
}

async function createAccount() {
  errorMessage.value = ''
  try {
    const payload = {
      ...form,
      company_id: form.role === 'platform_admin' ? null : form.company_id,
      must_change_password: true,
    }
    const user = await apiRequest<User>('/admin/users', { method: 'POST', body: JSON.stringify(payload) })
    users.value.unshift(user)
    Object.assign(form, { email: '', display_name: '', password: '', role: 'employee', company_id: '' })
    showCreate.value = false
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '账户创建失败' }
}

async function toggleStatus(user: User) {
  errorMessage.value = ''
  try {
    const updated = await apiRequest<User>(`/admin/users/${user.id}/status`, {
      method: 'PATCH', body: JSON.stringify({ is_active: !user.is_active }),
    })
    Object.assign(user, updated)
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '状态更新失败' }
}

async function submitReset() {
  if (!resetTarget.value) return
  errorMessage.value = ''
  try {
    await apiRequest<void>(`/admin/users/${resetTarget.value.id}/reset-password`, {
      method: 'POST', body: JSON.stringify({ new_password: resetPassword.value, must_change_password: true }),
    })
    resetTarget.value = null
    resetPassword.value = ''
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '密码重置失败' }
}

onMounted(async () => {
  try { await Promise.all([loadUsers(), loadCompanies()]) }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '初始化失败' }
})
</script>

<template>
  <AppShell>
    <header class="page-header compact">
      <div><p class="eyebrow">ADMINISTRATION</p><h1>账户管理</h1><p>创建账户、控制登录状态并执行安全密码重置。</p></div>
      <button class="primary-button" type="button" @click="showCreate = !showCreate">{{ showCreate ? '取消创建' : '创建账户' }}</button>
    </header>
    <div v-if="errorMessage" class="notice error" role="alert">{{ errorMessage }}</div>
    <form v-if="showCreate" class="panel inline-form" @submit.prevent="createAccount">
      <label><span>姓名</span><input v-model.trim="form.display_name" required maxlength="100" /></label>
      <label><span>邮箱</span><input v-model.trim="form.email" type="email" required /></label>
      <label><span>初始密码</span><input v-model="form.password" type="password" minlength="12" required /></label>
      <label><span>角色</span><select v-model="form.role"><option value="employee">普通员工</option><option value="sales">销售</option><option value="content_admin">内容管理员</option><option value="company_admin">企业管理员</option><option value="platform_admin">平台管理员</option></select></label>
      <label v-if="form.role !== 'platform_admin'"><span>所属企业</span><select v-model="form.company_id" required><option value="" disabled>请选择企业</option><option v-for="company in companies" :key="company.id" :value="company.id">{{ company.name }}</option></select></label>
      <button class="primary-button" type="submit">确认创建</button>
    </form>
    <section class="panel table-panel">
      <div v-if="loading" class="empty-state">正在加载账户…</div>
      <div v-else-if="!users.length" class="empty-state">暂无账户</div>
      <table v-else>
        <thead><tr><th>账户</th><th>企业</th><th>角色</th><th>状态</th><th>最近登录</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td><b>{{ user.display_name }}</b><small>{{ user.email }}</small></td>
            <td>{{ companyName(user.company_id) }}</td><td>{{ roleNames[user.role] ?? user.role }}</td>
            <td><span class="pill" :class="{ inactive: !user.is_active }">{{ user.is_active ? '已启用' : '已停用' }}</span></td>
            <td>{{ user.last_login_at ? new Date(user.last_login_at).toLocaleString() : '尚未登录' }}</td>
            <td class="actions">
              <button type="button" class="link-button" @click="resetTarget = user">重置密码</button>
              <button v-if="user.id !== authState.user?.id" type="button" class="link-button danger" @click="toggleStatus(user)">{{ user.is_active ? '停用' : '启用' }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
    <div v-if="resetTarget" class="modal-backdrop" @click.self="resetTarget = null">
      <form class="modal" @submit.prevent="submitReset">
        <p class="eyebrow">RESET PASSWORD</p><h2>重置 {{ resetTarget.display_name }} 的密码</h2>
        <p>完成后该用户的旧会话立即失效，并在下次登录时要求修改密码。</p>
        <label><span>临时密码</span><input v-model="resetPassword" type="password" minlength="12" required autofocus /></label>
        <div class="modal-actions"><button type="button" class="secondary-button" @click="resetTarget = null">取消</button><button class="primary-button" type="submit">确认重置</button></div>
      </form>
    </div>
  </AppShell>
</template>
