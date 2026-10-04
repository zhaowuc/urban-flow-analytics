<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Aim, Connection, DataLine, Warning } from '@element-plus/icons-vue'
import BaseChart from '../components/BaseChart.vue'
import CityMap from '../components/CityMap.vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import StatCard from '../components/StatCard.vue'
import http from '../utils/http'

const router = useRouter()
const loading = ref(true)
const data = ref({ summary: {}, hourly: [], transport_types: [], stations_top10: [], regions: [], od_top10: [], station_map: [], warnings: [], prediction_curve: [] })
const catalogStations = ref([])
const mapMode = ref('stations')
const selected = ref(null)
const load = async () => { loading.value = true; try { [data.value, catalogStations.value] = await Promise.all([http.get('/dashboard/overview'), http.get('/catalog/stations')]) } finally { loading.value = false } }
onMounted(load)
const lineOption = computed(() => ({
  grid: { left: 10, right: 18, top: 15, bottom: 0, containLabel: true }, tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', boundaryGap: false, data: data.value.hourly.map((i) => `${String(i.hour).padStart(2, '0')}:00`), axisLabel: { color: '#8b98aa', fontSize: 10 }, axisLine: { lineStyle: { color: '#e5eaf1' } } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf1f6' } }, axisLabel: { color: '#8b98aa', fontSize: 10 } },
  series: [{ name: '客流', type: 'line', smooth: .35, symbol: 'circle', symbolSize: 5, data: data.value.hourly.map((i) => i.passenger_flow), lineStyle: { color: '#2d70df', width: 2.5 }, itemStyle: { color: '#2d70df' }, areaStyle: { color: { type: 'linear', x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(45,112,223,.25)'},{offset:1,color:'rgba(45,112,223,.015)'}] } } }],
}))
const pieOption = computed(() => ({
  tooltip: { trigger: 'item' }, legend: { bottom: 0, icon: 'circle', itemWidth: 7, textStyle: { color: '#718097', fontSize: 10 } },
  color: ['#2563eb','#06b6d4','#12a874','#e6a23c','#8b5cf6'],
  series: [{ type: 'pie', radius: ['48%','72%'], center: ['50%','43%'], label: { show: false }, itemStyle: { borderColor: '#fff', borderWidth: 3 }, data: data.value.transport_types.map((i) => ({ name: ({metro:'地铁',bus:'公交',taxi:'出租车',bike:'共享单车',ride_hailing:'网约车'}[i.transport_type] || i.transport_type), value: i.passenger_flow })) }],
}))
const maxStation = computed(() => Math.max(1, ...data.value.stations_top10.map((i) => i.passenger_flow)))
const stationName = (code) => catalogStations.value.find((item) => item.station_id === code)?.station_name || code
const levelLabel = (l) => ({ normal:'正常',yellow:'黄色',orange:'橙色',red:'红色' }[l] || l)
</script>

<template>
  <div class="page" v-loading="loading">
    <PageHeader eyebrow="OVERVIEW" title="城市客流综合态势" description="统一观察离线分析、站点运行、OD 流向与预测预警结果。">
      <el-button @click="load">刷新数据</el-button><el-button type="primary" @click="router.push('/realtime')">进入实时监测</el-button>
    </PageHeader>
    <div class="notice-strip"><el-icon><Connection /></el-icon> 当前系统使用内置模拟城市交通数据集进行功能验证，地图、站点、线路及客流均为虚拟示例数据。</div>
    <div class="page-grid grid-4 section-gap">
      <StatCard label="今日总客流" :value="Number(data.summary.today_total || 0).toLocaleString()" unit="人次" :trend="`+${data.summary.yesterday_change_percent || 0}%`" note="较昨日" :icon="DataLine" />
      <StatCard label="当前时段客流" :value="Number(data.summary.current_flow || 0).toLocaleString()" unit="人次" note="最近分析时段" tone="cyan" :icon="Aim" />
      <StatCard label="未来 30 分钟" :value="Math.round(data.summary.predicted_30_minutes || 0).toLocaleString()" unit="人次" note="模型预测总量" tone="green" :icon="Connection" />
      <StatCard label="活动预警" :value="data.summary.warning_count || 0" unit="条" note="全系统一致状态" tone="orange" :icon="Warning" />
      <PanelCard class="span-3" title="星海示例市运行地图" subtitle="本地 GeoJSON · 点击站点查看容量、负载与预测">
        <template #actions><el-segmented v-model="mapMode" :options="[{label:'站点分布',value:'stations'},{label:'区域热力',value:'heat'},{label:'OD 流向',value:'od'}]" size="small" /></template>
        <CityMap :mode="mapMode" :stations="data.station_map" :regions="data.regions" :od="data.od_top10" height="470px" @station-click="selected = $event" />
      </PanelCard>
      <PanelCard title="热门站点 Top 10" subtitle="按分析周期累计客流排序">
        <div class="rank-list">
          <div v-for="(item,index) in data.stations_top10" :key="item.station_id" class="rank-item"><b>{{ String(index+1).padStart(2,'0') }}</b><span>{{ stationName(item.station_id) }}<small>{{ item.station_id }}</small></span><div><i :style="{width:`${item.passenger_flow/maxStation*100}%`}"></i></div><strong>{{ Number(item.passenger_flow).toLocaleString() }}</strong></div>
        </div>
      </PanelCard>
      <PanelCard class="span-3" title="全天客流变化" subtitle="Spark SQL 小时粒度统计结果"><BaseChart :option="lineOption" height="286px" /></PanelCard>
      <PanelCard title="出行方式构成" subtitle="五类交通方式占比"><BaseChart :option="pieOption" height="286px" /></PanelCard>
    </div>
    <el-drawer v-model="selected" size="360px" title="站点运行详情">
      <div v-if="selected" class="station-detail">
        <div class="station-code">{{ selected.station_id }}</div><h3>{{ selected.name }}</h3>
        <span :class="['level-pill',`level-${selected.warning_level}`]">{{ levelLabel(selected.warning_level) }}</span>
        <dl><div><dt>所属区域</dt><dd>{{ selected.region }}</dd></div><div><dt>当前客流</dt><dd>{{ selected.current_flow }}</dd></div><div><dt>站点容量</dt><dd>{{ selected.capacity }}</dd></div><div><dt>当前负载率</dt><dd>{{ (selected.load_rate*100).toFixed(1) }}%</dd></div><div><dt>未来 30 分钟</dt><dd>{{ selected.predicted_30 == null ? '待预测' : Math.round(selected.predicted_30) }}</dd></div></dl>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.rank-list{display:flex;flex-direction:column;gap:13px}.rank-item{display:grid;grid-template-columns:25px minmax(82px,1fr) 1fr 52px;align-items:center;gap:8px}.rank-item>b{color:#9aa8ba;font-size:10px}.rank-item>span{font-size:11px;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rank-item small{display:block;margin-top:3px;color:#a3adba;font-size:8px;font-weight:500}.rank-item>div{height:4px;overflow:hidden;border-radius:5px;background:#edf1f6}.rank-item i{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,#3477e5,#67a0f5)}.rank-item>strong{text-align:right;font-size:10px;font-variant-numeric:tabular-nums}.station-detail{text-align:center}.station-code{display:inline-block;padding:5px 8px;border-radius:6px;color:#316bc8;background:#edf4ff;font-size:10px;font-weight:700}.station-detail h3{margin:13px 0 9px}.station-detail dl{margin-top:28px;border-top:1px solid var(--line)}.station-detail dl div{display:flex;justify-content:space-between;padding:14px 2px;border-bottom:1px solid var(--line);font-size:12px}.station-detail dt{color:var(--text-400)}.station-detail dd{margin:0;font-weight:650}
</style>
