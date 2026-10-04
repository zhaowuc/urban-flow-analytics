<script setup>
defineProps({ title: String, subtitle: String, flush: Boolean })
</script>
<template>
  <section :class="['surface', flush ? '' : 'panel']">
    <div v-if="title" class="panel-head" :style="flush ? 'padding:20px 20px 0' : ''">
      <div><h2 class="panel-title">{{ title }}</h2><p v-if="subtitle" class="panel-subtitle">{{ subtitle }}</p></div>
      <div><slot name="actions" /></div>
    </div>
    <slot />
  </section>
</template>
