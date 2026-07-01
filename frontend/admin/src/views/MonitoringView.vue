<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiError, apiRequest } from '../auth'
import AppShell from '../components/AppShell.vue'
import type { Monitoring, RateMetric } from '../operations'
const metrics = ref<Monitoring | null>(null); const errorMessage = ref('')
const percent = (item: RateMetric) => item.success_rate == null ? '暂无数据' : `${(item.success_rate * 100).toFixed(1)}%`
async function load() { try { metrics.value = await apiRequest('/tenant/monitoring') } catch (error) { errorMessage.value = error instanceof ApiError ? error.message : '运行指标加载失败' } }
onMounted(load)
</script>
<template><AppShell><header class="page-header compact"><div><p class="eyebrow">OPERATIONS</p><h1>运行监控</h1><p>进程启动后的基础可用性、性能和业务主链路指标。</p></div><button class="secondary-button" @click="load">刷新</button></header><div v-if="errorMessage" class="notice error">{{ errorMessage }}</div><template v-if="metrics"><section class="metric-grid"><article><span>请求总量</span><strong>{{ metrics.requests }}</strong><p>服务进程累计请求</p></article><article><span>系统错误率</span><strong>{{ (metrics.error_rate * 100).toFixed(2) }}%</strong><p>{{ metrics.errors }} 次 5xx 错误</p></article><article><span>P95 响应</span><strong>{{ metrics.p95_duration_ms }} ms</strong><p>最近 5000 次请求</p></article></section><section class="funnel-grid operations-grid"><article class="panel"><span>名片发布成功率</span><b>{{ percent(metrics.card_publish) }}</b><small>{{ metrics.card_publish.successes }}/{{ metrics.card_publish.attempts }}</small></article><article class="panel"><span>公开页访问成功率</span><b>{{ percent(metrics.public_card) }}</b><small>{{ metrics.public_card.successes }}/{{ metrics.public_card.attempts }}</small></article><article class="panel"><span>留资提交成功率</span><b>{{ percent(metrics.lead_submit) }}</b><small>{{ metrics.lead_submit.successes }}/{{ metrics.lead_submit.attempts }}</small></article><article class="panel"><span>线索首次处理时长</span><b>{{ metrics.average_first_response_minutes == null ? '暂无数据' : `${metrics.average_first_response_minutes} 分钟` }}</b><small>从留资到领取</small></article></section></template></AppShell></template>
