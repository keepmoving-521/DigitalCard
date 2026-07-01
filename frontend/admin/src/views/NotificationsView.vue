<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError, apiRequest } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { NotificationItem, NotificationPage } from '../lead'
const page = ref<NotificationPage>({ items: [], unread_count: 0 }); const errorMessage = ref('')
async function load() { try { page.value = await apiRequest('/tenant/notifications') } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '通知加载失败' } }
async function markRead(item: NotificationItem) { if (item.read_at) return; await apiRequest(`/tenant/notifications/${item.id}/read`, { method: 'POST' }); await load() }
onMounted(load)
</script>
<template><AppShell><header class="page-header compact"><div><p class="eyebrow">NOTIFICATIONS</p><h1>站内通知</h1><p>未读 {{ page.unread_count }} 条</p></div></header><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div><section class="notification-list"><article v-for="item in page.items" :key="item.id" class="panel notification-item" :class="{ unread: !item.read_at }" @click="markRead(item)"><span></span><div><b>{{ item.title }}</b><p>{{ item.content }}</p><small>{{ new Date(item.created_at).toLocaleString() }}</small></div></article><div v-if="!page.items.length" class="panel empty-state">暂无通知</div></section></AppShell></template>
