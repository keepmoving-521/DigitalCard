<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ApiError, apiRequest } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { Employee } from '../employee'

const form = reactive({ phone: '', email: '', avatar_url: '', bio: '' })
const loading = ref(true); const message = ref(''); const errorMessage = ref('')
async function load() {
  try { const employee = await apiRequest<Employee>('/tenant/employees/me'); Object.assign(form, { phone: employee.phone ?? '', email: employee.email ?? '', avatar_url: employee.avatar_url ?? '', bio: employee.bio ?? '' }) }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '个人资料加载失败' }
  finally { loading.value = false }
}
async function save() {
  try { await apiRequest('/tenant/employees/me', { method: 'PATCH', body: JSON.stringify(Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value || null]))) }); message.value = '个人资料已保存' }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '个人资料保存失败' }
}
onMounted(load)
</script>
<template><AppShell><header class="page-header compact"><div><p class="eyebrow">MY PROFILE</p><h1>我的资料</h1><p>可编辑范围由企业管理员统一设定。</p></div></header><div v-if="message" class="notice success">{{ message }}</div><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div><form v-if="!loading && !errorMessage" class="panel form-panel" @submit.prevent="save"><label><span>手机号</span><input v-model.trim="form.phone" /></label><label><span>邮箱</span><input v-model.trim="form.email" type="email" /></label><label><span>头像地址</span><input v-model.trim="form.avatar_url" type="url" /></label><label><span>个人简介</span><textarea v-model.trim="form.bio" rows="5" /></label><button class="primary-button">保存资料</button></form></AppShell></template>
