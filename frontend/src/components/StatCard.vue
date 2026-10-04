<script setup>
import { computed } from 'vue'
const props = defineProps({ label: String, value: [String, Number], unit: String, note: String, trend: [String, Number], tone: { type: String, default: 'blue' }, icon: Object })
const trendPositive = computed(() => String(props.trend || '').trim().startsWith('+'))
</script>

<template>
  <section class="stat-card surface">
    <div class="stat-top">
      <div class="label">{{ label }}</div>
      <div :class="['icon-box', tone]"><el-icon v-if="icon"><component :is="icon" /></el-icon></div>
    </div>
    <div class="stat-value"><span class="metric-value">{{ value ?? '—' }}</span><small v-if="unit">{{ unit }}</small></div>
    <div class="stat-bottom"><span v-if="trend" :class="['trend', trendPositive ? 'up' : 'down']">{{ trend }}</span><span>{{ note }}</span></div>
  </section>
</template>

<style scoped>
.stat-card { min-height: 142px; padding: 19px 20px 17px; }
.stat-top { display:flex; align-items:center; justify-content:space-between; }
.label { color: var(--text-600); font-size: 12px; font-weight: 650; }
.icon-box { display:flex; align-items:center; justify-content:center; width:31px; height:31px; border-radius:9px; color:#2563eb; background:#edf4ff; }
.icon-box.cyan { color:#0787a0; background:#eaf9fc; }.icon-box.green{color:#087a55;background:#e9f8f2}.icon-box.orange{color:#c15a10;background:#fff1e8}
.stat-value { margin-top: 13px; display:flex; align-items:baseline; gap:6px; }
.metric-value { font-size: 27px; line-height: 35px; font-weight: 750; letter-spacing: -.04em; }
small { color: var(--text-400); font-size: 11px; }
.stat-bottom { margin-top: 9px; display:flex; gap:7px; color:var(--text-400); font-size:11px; }
.trend { font-weight:700; }.trend.up{color:var(--green)}.trend.down{color:var(--orange)}
</style>
