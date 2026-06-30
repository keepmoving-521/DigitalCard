<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ApiError, apiRequest, authState } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { Employee, EmployeePage, ImportResult } from '../employee'
import type { Department } from '../organization'

const employees = ref<Employee[]>([])
const departments = ref<Department[]>([])
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const loading = ref(true)
const message = ref('')
const errorMessage = ref('')
const showForm = ref(false)
const editTarget = ref<Employee | null>(null)
const inviteUrl = ref('')
const importResult = ref<ImportResult | null>(null)
const form = reactive({ employee_no: '', name: '', phone: '', email: '', position: '', bio: '', department_id: '', manager_id: '', user_id: '' })
const has = (permission: string) => authState.user?.permissions.includes(permission) ?? false
const flatDepartments = computed(() => {
  const values: Department[] = []
  const walk = (items: Department[]) => items.forEach((item) => { values.push(item); walk(item.children) })
  walk(departments.value)
  return values
})

async function loadEmployees() {
  loading.value = true
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const page = await apiRequest<EmployeePage>(`/tenant/employees?${query}`)
    employees.value = page.items; total.value = page.total
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '员工加载失败' }
  finally { loading.value = false }
}

async function loadDepartments() {
  try { departments.value = await apiRequest<Department[]>('/tenant/departments') }
  catch { departments.value = [] }
}

function resetForm() {
  Object.assign(form, { employee_no: '', name: '', phone: '', email: '', position: '', bio: '', department_id: '', manager_id: '', user_id: '' })
  editTarget.value = null; showForm.value = false
}

function edit(employee: Employee) {
  editTarget.value = employee; showForm.value = true
  Object.assign(form, {
    employee_no: employee.employee_no, name: employee.name, phone: employee.phone ?? '',
    email: employee.email ?? '', position: employee.position ?? '', bio: employee.bio ?? '',
    department_id: employee.department_id ?? '', manager_id: employee.manager_id ?? '',
    user_id: employee.user_id ?? '',
  })
}

async function save() {
  const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value || null]))
  try {
    if (editTarget.value) await apiRequest(`/tenant/employees/${editTarget.value.id}`, { method: 'PATCH', body: JSON.stringify(payload) })
    else await apiRequest('/tenant/employees', { method: 'POST', body: JSON.stringify(payload) })
    message.value = editTarget.value ? '员工资料已保存' : '员工已创建'; resetForm(); await loadEmployees()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '员工保存失败' }
}

async function toggleStatus(employee: Employee) {
  try {
    await apiRequest(`/tenant/employees/${employee.id}/status`, {
      method: 'POST', body: JSON.stringify({ status: employee.status === 'active' ? 'inactive' : 'active' }),
    })
    await loadEmployees()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '状态更新失败' }
}

async function invite(employee: Employee) {
  try {
    const result = await apiRequest<{ invite_url: string }>(`/tenant/employees/${employee.id}/invite`, {
      method: 'POST', body: JSON.stringify({ role: 'employee' }),
    })
    inviteUrl.value = result.invite_url
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '邀请生成失败' }
}

async function copyInviteUrl() {
  await window.navigator.clipboard.writeText(inviteUrl.value)
  message.value = '邀请链接已复制'
}

async function importCsv(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    importResult.value = await apiRequest<ImportResult>('/tenant/employees/import', {
      method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: await file.text(),
    })
    await loadEmployees()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '导入失败' }
  finally { input.value = '' }
}

onMounted(() => { void loadEmployees(); void loadDepartments() })
</script>

<template>
  <AppShell>
    <header class="page-header compact"><div><p class="eyebrow">EMPLOYEES</p><h1>员工管理</h1><p>维护员工档案、在职状态与登录账户邀请。</p></div><div class="header-actions"><label v-if="has('employee.import')" class="secondary-button file-button">批量导入 CSV<input type="file" accept=".csv,text/csv" @change="importCsv" /></label><button v-if="has('employee.create')" class="primary-button" type="button" @click="showForm = true">新增员工</button></div></header>
    <div v-if="message" class="notice success">{{ message }}</div><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div>
    <form class="panel employee-filters" @submit.prevent="loadEmployees"><input v-model.trim="keyword" placeholder="姓名、编号、手机或邮箱" /><select v-model="statusFilter"><option value="">全部状态</option><option value="active">在职</option><option value="inactive">离职</option></select><button class="secondary-button">查询</button><span>共 {{ total }} 人</span></form>
    <section class="panel table-panel"><div v-if="loading" class="empty-state">正在加载员工…</div><div v-else-if="!employees.length" class="empty-state">暂无员工</div><table v-else><thead><tr><th>员工</th><th>编号</th><th>职位</th><th>联系方式</th><th>账户</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="employee in employees" :key="employee.id"><td><b>{{ employee.name }}</b><small>{{ employee.bio || '暂无简介' }}</small></td><td>{{ employee.employee_no }}</td><td>{{ employee.position || '—' }}</td><td>{{ employee.phone || '—' }}<small>{{ employee.email || '—' }}</small></td><td>{{ employee.user_id ? '已关联' : '未开通' }}</td><td><span class="pill" :class="{ inactive: employee.status === 'inactive' }">{{ employee.status === 'active' ? '在职' : '离职' }}</span></td><td class="actions"><button v-if="has('employee.update')" class="link-button" @click="edit(employee)">编辑</button><button v-if="has('employee.invite') && employee.status === 'active'" class="link-button" @click="invite(employee)">{{ employee.user_id ? '重新邀请' : '邀请' }}</button><button v-if="has('employee.status')" class="link-button danger" @click="toggleStatus(employee)">{{ employee.status === 'active' ? '停用' : '恢复' }}</button></td></tr></tbody></table></section>
    <div v-if="showForm" class="modal-backdrop" @click.self="resetForm"><form class="modal employee-modal" @submit.prevent="save"><p class="eyebrow">EMPLOYEE PROFILE</p><h2>{{ editTarget ? '编辑员工' : '新增员工' }}</h2><div class="modal-grid"><label><span>员工编号</span><input v-model.trim="form.employee_no" required /></label><label><span>姓名</span><input v-model.trim="form.name" required /></label><label><span>手机号</span><input v-model.trim="form.phone" /></label><label><span>邮箱</span><input v-model.trim="form.email" type="email" /></label><label><span>职位</span><input v-model.trim="form.position" /></label><label><span>部门</span><select v-model="form.department_id"><option value="">暂不归属</option><option v-for="department in flatDepartments.filter(item => item.is_active)" :key="department.id" :value="department.id">{{ department.name }}</option></select></label><label><span>直属上级</span><select v-model="form.manager_id"><option value="">暂不设置</option><option v-for="manager in employees.filter(item => item.id !== editTarget?.id && item.status === 'active')" :key="manager.id" :value="manager.id">{{ manager.name }} · {{ manager.employee_no }}</option></select></label><label><span>既有登录账户 ID</span><input v-model.trim="form.user_id" placeholder="可留空，邀请时自动创建" /></label><label class="full-row"><span>个人简介</span><textarea v-model.trim="form.bio" rows="3" /></label></div><div class="modal-actions"><button class="secondary-button" type="button" @click="resetForm">取消</button><button class="primary-button">保存</button></div></form></div>
    <div v-if="inviteUrl" class="modal-backdrop" @click.self="inviteUrl = ''"><div class="modal"><p class="eyebrow">INVITATION</p><h2>邀请链接已生成</h2><p>请通过企业认可的安全渠道发送给员工。链接只展示本次。</p><input :value="inviteUrl" readonly /><div class="modal-actions"><button class="secondary-button" @click="inviteUrl = ''">关闭</button><button class="primary-button" @click="copyInviteUrl">复制链接</button></div></div></div>
    <div v-if="importResult" class="modal-backdrop" @click.self="importResult = null"><div class="modal"><p class="eyebrow">IMPORT RESULT</p><h2>导入完成</h2><p>成功 {{ importResult.succeeded }} 行，失败 {{ importResult.failed }} 行。</p><ul class="import-errors"><li v-for="row in importResult.results.filter(item => item.status === 'failed')" :key="row.row">第 {{ row.row }} 行：{{ row.message }}</li></ul><div class="modal-actions"><button class="primary-button" @click="importResult = null">知道了</button></div></div></div>
  </AppShell>
</template>
