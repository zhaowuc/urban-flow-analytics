<script setup>
import * as echarts from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import http from '../utils/http'

const props = defineProps({
  mode: { type: String, default: 'stations' },
  stations: { type: Array, default: () => [] },
  regions: { type: Array, default: () => [] },
  od: { type: Array, default: () => [] },
  height: { type: String, default: '470px' },
})
const emit = defineEmits(['station-click'])
const root = ref()
const ready = ref(false)
let chart
let observer
let catalogStations = []
let geojson
const stationMap = computed(() => {
  const merged = new Map(catalogStations.map((item) => [item.station_id, item]))
  props.stations.forEach((item) => merged.set(item.station_id, { ...merged.get(item.station_id), ...item }))
  return merged
})
const regionName = computed(() => Object.fromEntries((geojson?.features || []).map((f) => [f.properties.id, f.properties.name])))

const levelColor = (level) => ({ red: '#e5484d', orange: '#f97316', yellow: '#e6a23c', normal: '#2563eb' }[level] || '#2563eb')
const stationSeries = () => Array.from(stationMap.value.values()).map((s) => ({
  name: s.station_name,
  station_id: s.station_id,
  region: s.region || s.region_id,
  capacity: s.capacity,
  current_flow: Number(s.current_flow ?? s.passenger_flow ?? 0),
  predicted_30: s.predicted_30,
  load_rate: Number(s.load_rate ?? 0),
  warning_level: s.warning_level || 'normal',
  value: [Number(s.longitude), Number(s.latitude), Number(s.current_flow ?? s.passenger_flow ?? 0)],
  itemStyle: { color: levelColor(s.warning_level || 'normal') },
}))

const makeOption = () => {
  const common = {
    animationDuration: 650,
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', borderWidth: 0, backgroundColor: 'rgba(7,17,31,.92)', textStyle: { color: '#fff', fontSize: 12 } },
    geo: {
      map: 'demo-city', roam: true, zoom: 1.08, center: [104.7, 35.15],
      itemStyle: { areaColor: '#eef3fa', borderColor: '#fff', borderWidth: 1.5 },
      emphasis: { itemStyle: { areaColor: '#dce9fb' }, label: { color: '#20324e' } },
      label: { show: true, color: '#76859b', fontSize: 10 },
    },
  }
  if (props.mode === 'heat') {
    const values = props.regions.map((r) => ({ name: regionName.value[r.region_id || r.region] || r.region_name, value: Number(r.passenger_flow || 0), id: r.region_id || r.region }))
    const max = Math.max(1, ...values.map((v) => v.value))
    return {
      ...common,
      visualMap: { min: 0, max, left: 14, bottom: 14, calculable: false, text: ['高', '低'], textStyle: { color: '#78879b', fontSize: 10 }, inRange: { color: ['#eaf2ff', '#a7c7fb', '#4e86e5', '#174ca8'] } },
      series: [{ type: 'map', map: 'demo-city', geoIndex: 0, data: values, tooltip: { formatter: (p) => `${p.name}<br/>区域客流&nbsp;&nbsp;<b>${Number(p.value || 0).toLocaleString()}</b>` } }],
    }
  }
  const points = stationSeries()
  const baseScatter = {
    type: props.mode === 'realtime' ? 'effectScatter' : 'scatter', coordinateSystem: 'geo', data: points,
    symbolSize: (value) => Math.max(7, Math.min(25, 7 + Math.sqrt(Number(value[2] || 0)) * .65)),
    rippleEffect: { scale: 2.2, brushType: 'stroke' },
    itemStyle: { shadowBlur: 10, shadowColor: 'rgba(37,99,235,.25)' },
    emphasis: { scale: 1.45 }, zlevel: 3,
    tooltip: { formatter: (p) => {
      const d = p.data
      return `<b>${d.name}</b> <span style="opacity:.65">${d.station_id}</span><br/>当前客流&nbsp;&nbsp;${d.current_flow.toLocaleString()}<br/>站点容量&nbsp;&nbsp;${d.capacity ?? '—'}<br/>当前负载率&nbsp;&nbsp;${(d.load_rate * 100).toFixed(1)}%<br/>未来30分钟&nbsp;&nbsp;${d.predicted_30 == null ? '待预测' : Math.round(d.predicted_30)}<br/>预警等级&nbsp;&nbsp;${d.warning_level}`
    } },
  }
  if (props.mode === 'od') {
    const lines = props.od.map((item) => {
      const from = stationMap.value.get(item.origin_station)
      const to = stationMap.value.get(item.destination_station)
      return from && to ? { fromName: from.station_name, toName: to.station_name, value: Number(item.passenger_flow), coords: [[from.longitude, from.latitude], [to.longitude, to.latitude]] } : null
    }).filter(Boolean)
    return {
      ...common,
      series: [
        { type: 'lines', coordinateSystem: 'geo', data: lines, zlevel: 2, effect: { show: true, period: 4, trailLength: .18, symbol: 'arrow', symbolSize: 5 }, lineStyle: { color: '#2b6fe8', width: 1.5, opacity: .62, curveness: .22 }, tooltip: { formatter: (p) => `${p.data.fromName} → ${p.data.toName}<br/>OD 客流&nbsp;&nbsp;<b>${p.data.value.toLocaleString()}</b>` } },
        { ...baseScatter, type: 'scatter', symbolSize: 7, data: points.filter((p) => props.od.some((o) => o.origin_station === p.station_id || o.destination_station === p.station_id)) },
      ],
    }
  }
  return { ...common, series: [baseScatter] }
}

const render = () => { if (ready.value && chart) chart.setOption(makeOption(), true) }
onMounted(async () => {
  ;[geojson, catalogStations] = await Promise.all([http.get('/catalog/geojson'), http.get('/catalog/stations')])
  echarts.registerMap('demo-city', geojson)
  chart = echarts.init(root.value)
  chart.on('click', (params) => { if (params.data?.station_id) emit('station-click', params.data) })
  ready.value = true
  render()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(root.value)
})
watch(() => [props.mode, props.stations, props.regions, props.od], render, { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>

<template>
  <div class="map-wrap" :style="{ height }">
    <div ref="root" class="map-root" />
    <div v-if="!ready" class="map-loading">正在加载本地虚拟城市地图…</div>
    <div class="map-watermark">VIRTUAL DEMO CITY · LOCAL GEOJSON</div>
  </div>
</template>

<style scoped>
.map-wrap { position: relative; width:100%; min-height: 360px; overflow:hidden; border-radius: 10px; background: radial-gradient(circle at 50% 45%, #f9fbfe, #f1f5fa); }
.map-root { width:100%; height:100%; }
.map-loading { position:absolute; inset:0; display:grid; place-items:center; color:var(--text-400); font-size:12px; }
.map-watermark { position:absolute; right:14px; bottom:10px; color:#a8b3c3; font-size:9px; font-weight:700; letter-spacing:.1em; pointer-events:none; }
</style>
