<script setup lang="ts">
import { authState } from '../auth'
import AppShell from '../components/AppShell.vue'
</script>

<template>
  <AppShell>
    <header class="page-header">
      <div>
        <p class="eyebrow">OVERVIEW</p>
        <h1>你好，{{ authState.user?.display_name }}</h1>
        <p>账户与安全底座已经就绪，后续业务模块将在这里逐步展开。</p>
      </div>
      <span class="status"><i /> 账户安全</span>
    </header>
    <section class="metric-grid">
      <article><span>当前角色</span><strong>{{ authState.user?.role === 'admin' ? '管理员' : '普通用户' }}</strong><p>权限由服务端与路由双重校验</p></article>
      <article><span>登录保护</span><strong>已启用</strong><p>失败锁定与登录审计持续生效</p></article>
      <article><span>会话策略</span><strong>15 分钟</strong><p>访问令牌短期有效并支持安全刷新</p></article>
    </section>
    <section class="next-card">
      <div><p class="eyebrow">NEXT ITERATION</p><h2>V0.3.0 · 企业、租户与权限</h2></div>
      <span>计划中</span>
    </section>
  </AppShell>
</template>

