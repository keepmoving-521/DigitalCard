<script setup lang="ts">
import AppShell from '../components/AppShell.vue'
</script>

<template>
  <AppShell>
    <section class="state-page">
      <span class="state-code">403</span>
      <p class="eyebrow">ACCESS DENIED</p>
      <h1>你没有访问此页面的权限</h1>
      <p>当前账户权限不足。如需访问，请联系企业管理员。</p>
      <RouterLink class="primary-button" to="/dashboard">返回工作台</RouterLink>
    </section>
  </AppShell>
</template>

