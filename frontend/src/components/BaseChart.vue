<script setup>
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
const props = defineProps({ option: { type: Object, required: true }, height: { type: String, default: '320px' } })
const root = ref()
let chart
let observer
const render = () => chart?.setOption(props.option, true)
onMounted(() => {
  chart = echarts.init(root.value)
  render()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(root.value)
})
watch(() => props.option, render, { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template><div ref="root" :style="{ height, width: '100%' }" /></template>
