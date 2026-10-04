<script setup>
defineProps({ title: String, eyebrow: String, description: String })
</script>

<template>
  <header class="page-header">
    <div>
      <div class="eyebrow">{{ eyebrow }}</div>
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div class="header-actions"><slot /></div>
  </header>
</template>

<style scoped>
.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.eyebrow { color: #3e73cf; font-size: 10px; font-weight: 800; letter-spacing: .16em; margin-bottom: 7px; }
h1 { margin: 0; font-size: 25px; line-height: 34px; letter-spacing: -.035em; }
p { margin: 7px 0 0; max-width: 720px; color: var(--text-600); font-size: 13px; line-height: 21px; }
.header-actions { display: flex; align-items: center; gap: 10px; }
</style>
