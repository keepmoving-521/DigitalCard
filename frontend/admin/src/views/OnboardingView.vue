<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError, apiRequest } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { OnboardingStatus } from '../operations'
const status = ref<OnboardingStatus | null>(null); const errorMessage = ref('')
async function load() { try { status.value = await apiRequest('/tenant/onboarding') } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '初始化状态加载失败' } }
onMounted(load)
</script>
<template><AppShell><header class="page-header compact"><div><p class="eyebrow">GETTING STARTED</p><h1>企业初始化向导</h1><p>按顺序完成企业、组织、员工和首张名片配置。</p></div><span v-if="status" class="status"><i />{{ status.completed_count }}/{{ status.total_count }}</span></header><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div><section v-if="status" class="onboarding-list"><RouterLink v-for="(step, index) in status.steps" :key="step.code" :to="step.path" class="panel onboarding-step" :class="{ done: step.completed }"><span>{{ step.completed ? '✓' : index + 1 }}</span><div><b>{{ step.name }}</b><small>{{ step.completed ? '已完成，可随时再次维护' : '点击进入配置' }}</small></div><i>›</i></RouterLink></section><section v-if="status?.completed" class="notice success">初始化已完成。现在可以分享名片、接收客户咨询并在客户中心跟进。</section></AppShell></template>
