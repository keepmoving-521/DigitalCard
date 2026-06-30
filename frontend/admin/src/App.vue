<script setup lang="ts">
const apiDocsUrl = `${import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '') ?? 'http://localhost:8000'}/docs`
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <a class="brand" href="/" aria-label="DigitalCard 首页">
        <span class="brand-mark">D</span>
        <span>DigitalCard</span>
      </a>
      <nav aria-label="主导航">
        <a class="nav-item active" href="#overview">工程概览</a>
        <a class="nav-item" :href="apiDocsUrl" target="_blank" rel="noreferrer">API 文档</a>
      </nav>
      <span class="version">V0.1.0 · 工程底座</span>
    </aside>

    <main id="overview">
      <header>
        <div>
          <p class="eyebrow">WELCOME BACK</p>
          <h1>DigitalCard 管理端</h1>
          <p class="subtitle">基础工程已经就绪，下一步将在这里构建企业与名片管理能力。</p>
        </div>
        <span class="status"><i /> 系统运行中</span>
      </header>

      <section class="cards" aria-label="工程状态">
        <article>
          <span class="number">01</span>
          <h2>FastAPI 服务</h2>
          <p>统一响应、请求日志、健康检查与自动 API 文档已接入。</p>
        </article>
        <article>
          <span class="number">02</span>
          <h2>Vue 3 管理端</h2>
          <p>TypeScript、Vite、组件测试与生产构建流程已经准备完成。</p>
        </article>
        <article>
          <span class="number">03</span>
          <h2>持续交付</h2>
          <p>代码检查、自动化测试、数据库迁移和容器配置保持一致。</p>
        </article>
      </section>

      <section class="next-step">
        <div>
          <p class="eyebrow">NEXT ITERATION</p>
          <h2>V0.2.0 · 账户与登录</h2>
        </div>
        <span>计划中</span>
      </section>
    </main>
  </div>
</template>

