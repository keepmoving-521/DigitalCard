<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ApiError, apiRequest, authState } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { Company } from '../organization'

const loading = ref(true)
const saving = ref(false)
const message = ref('')
const errorMessage = ref('')
const canEdit = () => authState.user?.permissions.includes('company.update') ?? false
const form = reactive({ name: '', logo_url: '', description: '', contact_name: '', contact_email: '', contact_phone: '', address: '', inactive_employee_visibility: 'hidden', employee_self_editable_fields: [] as string[] })
const selfFields = [{ code: 'avatar_url', name: '头像' }, { code: 'phone', name: '手机号' }, { code: 'email', name: '邮箱' }, { code: 'bio', name: '个人简介' }]
const code = ref('')

async function loadCompany() {
  try {
    const company = await apiRequest<Company>('/tenant/company')
    code.value = company.code
    Object.assign(form, {
      name: company.name, logo_url: company.logo_url ?? '', description: company.description ?? '',
      contact_name: company.contact_name ?? '', contact_email: company.contact_email ?? '',
      contact_phone: company.contact_phone ?? '', address: company.address ?? '',
      inactive_employee_visibility: company.inactive_employee_visibility,
      employee_self_editable_fields: [...company.employee_self_editable_fields],
    })
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '企业资料加载失败' }
  finally { loading.value = false }
}

async function save() {
  saving.value = true; message.value = ''; errorMessage.value = ''
  try {
    await apiRequest<Company>('/tenant/company', {
      method: 'PUT',
      body: JSON.stringify(Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value || null]))),
    })
    message.value = '企业资料已保存'
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '企业资料保存失败' }
  finally { saving.value = false }
}

onMounted(loadCompany)
</script>

<template>
  <AppShell>
    <header class="page-header compact"><div><p class="eyebrow">COMPANY</p><h1>企业设置</h1><p>统一维护企业品牌、介绍与对外联系方式。</p></div><span class="status"><i /> {{ code }}</span></header>
    <div v-if="message" class="notice success">{{ message }}</div><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div>
    <div v-if="loading" class="panel empty-state">正在加载企业资料…</div>
    <form v-else class="panel form-panel company-settings" @submit.prevent="save">
      <label><span>企业名称</span><input v-model.trim="form.name" :disabled="!canEdit()" required /></label>
      <label><span>Logo 地址</span><input v-model.trim="form.logo_url" :disabled="!canEdit()" type="url" /></label>
      <label class="full-row"><span>企业简介</span><textarea v-model.trim="form.description" :disabled="!canEdit()" rows="5" /></label>
      <label><span>联系人</span><input v-model.trim="form.contact_name" :disabled="!canEdit()" /></label>
      <label><span>联系邮箱</span><input v-model.trim="form.contact_email" :disabled="!canEdit()" type="email" /></label>
      <label><span>联系电话</span><input v-model.trim="form.contact_phone" :disabled="!canEdit()" /></label>
      <label><span>企业地址</span><input v-model.trim="form.address" :disabled="!canEdit()" /></label>
      <label><span>离职员工公开展示</span><select v-model="form.inactive_employee_visibility" :disabled="!canEdit()"><option value="hidden">隐藏公开资料</option><option value="show_inactive">显示并标记离职</option></select></label>
      <fieldset class="full-row policy-fields"><legend>员工可自行维护的字段</legend><label v-for="field in selfFields" :key="field.code"><input v-model="form.employee_self_editable_fields" type="checkbox" :value="field.code" :disabled="!canEdit()" />{{ field.name }}</label></fieldset>
      <button v-if="canEdit()" class="primary-button" type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存资料' }}</button>
      <p v-else class="password-rules">当前角色只有查看权限。</p>
    </form>
  </AppShell>
</template>
