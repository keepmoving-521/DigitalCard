<script setup lang="ts">
import { authState } from '../auth'
import AppShell from '../components/AppShell.vue'

const roleNames: Record<string, string> = {
  platform_admin: '平台管理员',
  company_admin: '企业管理员',
  content_admin: '内容管理员',
  sales: '销售',
  employee: '普通员工',
}
</script>

<template>
  <AppShell>
    <header class="page-header">
      <div>
        <p class="eyebrow">OVERVIEW</p>
        <h1>你好，{{ authState.user?.display_name }}</h1>
        <p>创建、分享、留资、跟进主链路已达到首批企业试用标准。</p>
      </div>
      <span class="status"><i /> 账户安全</span>
    </header>
    <section class="metric-grid">
      <article><span>当前角色</span><strong>{{ roleNames[authState.user?.role ?? ''] ?? '未知角色' }}</strong><p>权限由服务端与路由双重校验</p></article>
      <article><span>登录保护</span><strong>已启用</strong><p>失败锁定与登录审计持续生效</p></article>
      <article><span>会话策略</span><strong>15 分钟</strong><p>访问令牌短期有效并支持安全刷新</p></article>
    </section>
    <section class="next-card">
      <div><p class="eyebrow">OPEN PLATFORM</p><h2>V1.5.0 · 消息中心与开放平台</h2></div>
      <span>稳定版</span>
    </section>
  </AppShell>
</template>
