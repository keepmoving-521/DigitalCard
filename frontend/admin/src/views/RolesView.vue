<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ApiError, apiRequest, authState } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { PermissionDefinition, TenantRole } from '../organization'

const roles = ref<TenantRole[]>([])
const permissions = ref<PermissionDefinition[]>([])
const selected = ref<TenantRole | null>(null)
const draft = ref<string[]>([])
const errorMessage = ref('')
const message = ref('')
const canEdit = computed(() => authState.user?.permissions.includes('role.update') ?? false)
const categories = computed(() =>
  permissions.value.reduce<Record<string, PermissionDefinition[]>>((groups, item) => {
    ;(groups[item.category] ??= []).push(item)
    return groups
  }, {}),
)

async function load() {
  try { [roles.value, permissions.value] = await Promise.all([apiRequest<TenantRole[]>('/tenant/roles'), apiRequest<PermissionDefinition[]>('/tenant/permissions')]); selectRole(roles.value[0] ?? null) }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '角色权限加载失败' }
}

function selectRole(role: TenantRole | null) { selected.value = role; draft.value = role ? [...role.permissions] : [] }
function toggle(code: string) { draft.value = draft.value.includes(code) ? draft.value.filter((item) => item !== code) : [...draft.value, code] }
async function save() {
  if (!selected.value) return
  try {
    selected.value = await apiRequest<TenantRole>(`/tenant/roles/${selected.value.code}/permissions`, { method: 'PUT', body: JSON.stringify({ permissions: draft.value }) })
    const index = roles.value.findIndex((role) => role.id === selected.value?.id); if (index >= 0) roles.value[index] = selected.value
    message.value = '角色权限已保存'
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '权限保存失败' }
}
onMounted(load)
</script>

<template><AppShell><header class="page-header compact"><div><p class="eyebrow">ACCESS CONTROL</p><h1>角色权限</h1><p>企业预置角色的权限修改会立即作用于对应用户。</p></div></header><div v-if="message" class="notice success">{{ message }}</div><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div>
  <div class="role-layout"><aside class="panel role-list"><button v-for="role in roles" :key="role.id" type="button" :class="{ active: selected?.id === role.id }" @click="selectRole(role)"><b>{{ role.name }}</b><small>{{ role.description }}</small></button></aside>
    <section v-if="selected" class="panel permission-panel"><div class="permission-heading"><div><h2>{{ selected.name }}</h2><p>{{ selected.code === 'company_admin' ? '企业管理员权限受保护，避免企业失去管理能力。' : '按业务职责分配最小必要权限。' }}</p></div><button v-if="canEdit && selected.code !== 'company_admin'" class="primary-button" type="button" @click="save">保存权限</button></div>
      <section v-for="(items, category) in categories" :key="category" class="permission-group"><h3>{{ category }}</h3><div class="permission-grid"><button v-for="permission in items" :key="permission.code" type="button" class="permission-item" :class="{ selected: draft.includes(permission.code) }" :disabled="!canEdit || selected.code === 'company_admin'" @click="toggle(permission.code)"><span>{{ draft.includes(permission.code) ? '✓' : '' }}</span><div><b>{{ permission.name }}</b><small>{{ permission.code }}</small></div></button></div></section>
    </section></div>
</AppShell></template>
