<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ApiError, apiRequest, authState } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { Department } from '../organization'

const departments = ref<Department[]>([])
const loading = ref(true)
const errorMessage = ref('')
const showCreate = ref(false)
const editTarget = ref<Department | null>(null)
const moveTarget = ref<Department | null>(null)
const createForm = reactive({ code: '', name: '', parent_id: '', sort_order: 0 })
const editForm = reactive({ code: '', name: '', sort_order: 0 })
const moveForm = reactive({ parent_id: '', sort_order: 0 })
const has = (permission: string) => authState.user?.permissions.includes(permission) ?? false

const flatDepartments = computed(() => {
  const result: Array<{ department: Department; depth: number }> = []
  const walk = (items: Department[], depth: number) => items.forEach((department) => {
    result.push({ department, depth }); walk(department.children, depth + 1)
  })
  walk(departments.value, 0)
  return result
})

async function loadDepartments() {
  loading.value = true
  try { departments.value = await apiRequest<Department[]>('/tenant/departments') }
  catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '部门加载失败' }
  finally { loading.value = false }
}

async function createDepartment() {
  try {
    await apiRequest('/tenant/departments', {
      method: 'POST', body: JSON.stringify({ ...createForm, parent_id: createForm.parent_id || null }),
    })
    Object.assign(createForm, { code: '', name: '', parent_id: '', sort_order: 0 })
    showCreate.value = false; await loadDepartments()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '部门创建失败' }
}

function startEdit(department: Department) {
  editTarget.value = department
  Object.assign(editForm, { code: department.code, name: department.name, sort_order: department.sort_order })
}

async function saveEdit() {
  if (!editTarget.value) return
  try {
    await apiRequest(`/tenant/departments/${editTarget.value.id}`, {
      method: 'PATCH', body: JSON.stringify(editForm),
    })
    editTarget.value = null; await loadDepartments()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '部门保存失败' }
}

function startMove(department: Department) {
  moveTarget.value = department
  Object.assign(moveForm, { parent_id: department.parent_id ?? '', sort_order: department.sort_order })
}

async function saveMove() {
  if (!moveTarget.value) return
  try {
    await apiRequest(`/tenant/departments/${moveTarget.value.id}/move`, {
      method: 'POST', body: JSON.stringify({ ...moveForm, parent_id: moveForm.parent_id || null }),
    })
    moveTarget.value = null; await loadDepartments()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '部门移动失败' }
}

async function toggleStatus(department: Department) {
  errorMessage.value = ''
  try {
    await apiRequest(`/tenant/departments/${department.id}/status`, {
      method: 'POST', body: JSON.stringify({ is_active: !department.is_active }),
    })
    await loadDepartments()
  } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '部门状态更新失败' }
}

onMounted(loadDepartments)
</script>

<template>
  <AppShell>
    <header class="page-header compact"><div><p class="eyebrow">ORGANIZATION</p><h1>部门管理</h1><p>维护企业部门树、顺序和启用状态。</p></div><button v-if="has('department.create')" class="primary-button" type="button" @click="showCreate = !showCreate">{{ showCreate ? '取消创建' : '创建部门' }}</button></header>
    <div v-if="errorMessage" class="notice error">{{ errorMessage }}</div>
    <form v-if="showCreate" class="panel inline-form department-form" @submit.prevent="createDepartment">
      <label><span>部门编号</span><input v-model.trim="createForm.code" required /></label><label><span>部门名称</span><input v-model.trim="createForm.name" required /></label>
      <label><span>上级部门</span><select v-model="createForm.parent_id"><option value="">顶级部门</option><option v-for="item in flatDepartments" :key="item.department.id" :value="item.department.id">{{ '—'.repeat(item.depth) }} {{ item.department.name }}</option></select></label>
      <label><span>排序</span><input v-model.number="createForm.sort_order" type="number" min="0" /></label><button class="primary-button" type="submit">确认创建</button>
    </form>
    <section class="panel table-panel"><div v-if="loading" class="empty-state">正在加载部门…</div><div v-else-if="!flatDepartments.length" class="empty-state">暂无部门</div>
      <table v-else><thead><tr><th>部门</th><th>编号</th><th>层级</th><th>排序</th><th>状态</th><th>操作</th></tr></thead><tbody>
        <tr v-for="item in flatDepartments" :key="item.department.id"><td><b :style="{ paddingLeft: `${item.depth * 22}px` }">{{ item.depth ? '↳ ' : '' }}{{ item.department.name }}</b></td><td>{{ item.department.code }}</td><td>{{ item.depth + 1 }}</td><td>{{ item.department.sort_order }}</td><td><span class="pill" :class="{ inactive: !item.department.is_active }">{{ item.department.is_active ? '已启用' : '已停用' }}</span></td>
          <td class="actions"><button v-if="has('department.update')" class="link-button" type="button" @click="startEdit(item.department)">编辑</button><button v-if="has('department.move')" class="link-button" type="button" @click="startMove(item.department)">移动</button><button v-if="has('department.disable')" class="link-button danger" type="button" @click="toggleStatus(item.department)">{{ item.department.is_active ? '停用' : '启用' }}</button></td></tr>
      </tbody></table>
    </section>
    <div v-if="editTarget" class="modal-backdrop" @click.self="editTarget = null"><form class="modal" @submit.prevent="saveEdit"><p class="eyebrow">EDIT DEPARTMENT</p><h2>编辑部门</h2><label><span>编号</span><input v-model.trim="editForm.code" required /></label><label><span>名称</span><input v-model.trim="editForm.name" required /></label><label><span>排序</span><input v-model.number="editForm.sort_order" type="number" min="0" /></label><div class="modal-actions"><button class="secondary-button" type="button" @click="editTarget = null">取消</button><button class="primary-button">保存</button></div></form></div>
    <div v-if="moveTarget" class="modal-backdrop" @click.self="moveTarget = null"><form class="modal" @submit.prevent="saveMove"><p class="eyebrow">MOVE DEPARTMENT</p><h2>移动 {{ moveTarget.name }}</h2><label><span>上级部门</span><select v-model="moveForm.parent_id"><option value="">顶级部门</option><option v-for="item in flatDepartments.filter((row) => row.department.id !== moveTarget?.id)" :key="item.department.id" :value="item.department.id">{{ '—'.repeat(item.depth) }} {{ item.department.name }}</option></select></label><label><span>排序</span><input v-model.number="moveForm.sort_order" type="number" min="0" /></label><div class="modal-actions"><button class="secondary-button" type="button" @click="moveTarget = null">取消</button><button class="primary-button">确认移动</button></div></form></div>
  </AppShell>
</template>

