<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ApiError, apiRequest } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { Company } from '../organization'

const companies = ref<Company[]>([])
const loading = ref(true)
const showCreate = ref(false)
const errorMessage = ref('')
const form = reactive({ code: '', name: '', contact_name: '', contact_phone: '' })

async function loadCompanies() {
  loading.value = true
  try { companies.value = await apiRequest<Company[]>('/platform/companies') }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '企业加载失败' }
  finally { loading.value = false }
}

async function createCompany() {
  errorMessage.value = ''
  try {
    const company = await apiRequest<Company>('/platform/companies', {
      method: 'POST', body: JSON.stringify(form),
    })
    companies.value.unshift(company)
    Object.assign(form, { code: '', name: '', contact_name: '', contact_phone: '' })
    showCreate.value = false
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '企业创建失败' }
}

async function toggleStatus(company: Company) {
  errorMessage.value = ''
  try {
    const updated = await apiRequest<Company>(`/platform/companies/${company.id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: company.status === 'active' ? 'suspended' : 'active' }),
    })
    Object.assign(company, updated)
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '状态更新失败' }
}

onMounted(loadCompanies)
</script>

<template>
  <AppShell>
    <header class="page-header compact">
      <div><p class="eyebrow">PLATFORM</p><h1>企业管理</h1><p>创建企业空间并控制租户生命周期。暂停后企业用户将立即失去访问权限。</p></div>
      <button class="primary-button" type="button" @click="showCreate = !showCreate">{{ showCreate ? '取消创建' : '创建企业' }}</button>
    </header>
    <div v-if="errorMessage" class="notice error" role="alert">{{ errorMessage }}</div>
    <form v-if="showCreate" class="panel inline-form company-form" @submit.prevent="createCompany">
      <label><span>企业编号</span><input v-model.trim="form.code" required pattern="[a-zA-Z0-9_-]{2,64}" /></label>
      <label><span>企业名称</span><input v-model.trim="form.name" required maxlength="160" /></label>
      <label><span>联系人</span><input v-model.trim="form.contact_name" maxlength="100" /></label>
      <label><span>联系电话</span><input v-model.trim="form.contact_phone" maxlength="50" /></label>
      <button class="primary-button" type="submit">确认创建</button>
    </form>
    <section class="panel table-panel">
      <div v-if="loading" class="empty-state">正在加载企业…</div>
      <div v-else-if="!companies.length" class="empty-state">暂无企业空间</div>
      <table v-else>
        <thead><tr><th>企业</th><th>编号</th><th>联系方式</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="company in companies" :key="company.id">
          <td><b>{{ company.name }}</b><small>{{ company.contact_name || '未设置联系人' }}</small></td>
          <td>{{ company.code }}</td><td>{{ company.contact_phone || '—' }}</td>
          <td><span class="pill" :class="{ inactive: company.status !== 'active' }">{{ company.status === 'active' ? '正常' : '已暂停' }}</span></td>
          <td>{{ new Date(company.created_at).toLocaleString() }}</td>
          <td><button type="button" class="link-button" :class="{ danger: company.status === 'active' }" @click="toggleStatus(company)">{{ company.status === 'active' ? '暂停' : '恢复' }}</button></td>
        </tr></tbody>
      </table>
    </section>
  </AppShell>
</template>

