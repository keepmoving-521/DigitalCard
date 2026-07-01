<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ApiError, apiRequest } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { NotificationItem, NotificationPage } from '../lead'
const page = ref<NotificationPage>({ items: [], unread_count: 0 }); const errorMessage = ref('')
const preferences = reactive({ new_lead: true, follow_up_due: true, quota_warning: true })
async function load() { try { await apiRequest('/tenant/notifications/reminders/sync', { method: 'POST' }); const [items, values] = await Promise.all([apiRequest<NotificationPage>('/tenant/notifications'), apiRequest<typeof preferences>('/tenant/notifications/preferences')]); page.value = items; Object.assign(preferences, values) } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '通知加载失败' } }
async function markRead(item: NotificationItem) { if (item.read_at) return; await apiRequest(`/tenant/notifications/${item.id}/read`, { method: 'POST' }); await load() }
async function readAll() { await apiRequest('/tenant/notifications/read-all', { method: 'POST' }); await load() }
async function savePreferences() { await apiRequest('/tenant/notifications/preferences', { method: 'PUT', body: JSON.stringify(preferences) }) }
onMounted(load)
</script>
<template><AppShell><header class="page-header compact"><div><p class="eyebrow">NOTIFICATIONS</p><h1>站内通知</h1><p>未读 {{ page.unread_count }} 条</p></div><button v-if="page.unread_count" class="secondary-button" @click="readAll">全部已读</button></header><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div><form class="panel inline-form" @submit.prevent="savePreferences"><b>消息偏好</b><label class="checkbox-row"><input v-model="preferences.new_lead" type="checkbox" />新线索</label><label class="checkbox-row"><input v-model="preferences.follow_up_due" type="checkbox" />待跟进</label><label class="checkbox-row"><input v-model="preferences.quota_warning" type="checkbox" />配额预警</label><button class="secondary-button">保存偏好</button></form><section class="notification-list"><article v-for="item in page.items" :key="item.id" class="panel notification-item" :class="{ unread: !item.read_at }" @click="markRead(item)"><span></span><div><b>{{ item.title }}</b><p>{{ item.content }}</p><small>{{ new Date(item.created_at).toLocaleString() }}</small></div></article><div v-if="!page.items.length" class="panel empty-state">暂无通知</div></section></AppShell></template>
