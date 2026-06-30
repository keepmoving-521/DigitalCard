<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError, apiRequest } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { TenantAudit } from '../organization'

const audits = ref<TenantAudit[]>([])
const loading = ref(true)
const errorMessage = ref('')
const actionNames: Record<string, string> = {
  'company.created': '企业空间创建', 'company.status_changed': '企业状态变更',
  'company.profile_updated': '企业资料更新', 'department.created': '部门创建',
  'department.updated': '部门更新', 'department.moved': '部门移动',
  'department.status_changed': '部门状态变更', 'role.permissions_updated': '角色权限更新',
}
onMounted(async () => { try { audits.value = await apiRequest('/tenant/audits') } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '审计记录加载失败' } finally { loading.value = false } })
</script>

<template><AppShell><header class="page-header compact"><div><p class="eyebrow">AUDIT TRAIL</p><h1>变更审计</h1><p>追踪企业资料、部门和角色权限的关键变更。</p></div></header><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div><section class="panel table-panel"><div v-if="loading" class="empty-state">正在加载审计记录…</div><div v-else-if="!audits.length" class="empty-state">暂无变更记录</div><table v-else><thead><tr><th>时间</th><th>操作</th><th>对象</th><th>操作人</th><th>变更摘要</th></tr></thead><tbody><tr v-for="audit in audits" :key="audit.id"><td>{{ new Date(audit.created_at).toLocaleString() }}</td><td><b>{{ actionNames[audit.action] ?? audit.action }}</b></td><td>{{ audit.target_type }}<small>{{ audit.target_id }}</small></td><td>{{ audit.actor_user_id || '系统' }}</td><td><code>{{ audit.changes ? JSON.stringify(audit.changes) : '—' }}</code></td></tr></tbody></table></section></AppShell></template>

