<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Histogram, Timer } from '@element-plus/icons-vue'
import BaseChart from '../components/BaseChart.vue'
import CityMap from '../components/CityMap.vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import StatCard from '../components/StatCard.vue'
import http from '../utils/http'

const result=ref({summary:{},totals:{day:[]},hourly:[],regions:[],stations_top10:[],routes_top10:[],od_top10:[]})
const task=ref({})
const tasks=ref([])
const loading=ref(false)
const running=ref(false)
const tab=ref('trend')
let timer
const statusType=(s)=>({completed:'success',processing:'warning',failed:'danger',pending:'info'}[s]||'info')
const statusLabel=(s)=>({completed:'已完成',processing:'运行中',failed:'失败',pending:'排队中'}[s]||s)
const load=async()=>{ loading.value=true; try { const latest=await http.get('/analysis/latest'); task.value=latest.task;result.value=latest.result;tasks.value=await http.get('/analysis/tasks') } finally{loading.value=false} }
onMounted(load)
const start=async()=>{ running.value=true; const created=await http.post('/analysis/tasks',{analysis_type:'full',parameters:{top_n:10}}); ElMessage.success(`分析任务 #${created.id} 已启动`); clearInterval(timer); timer=setInterval(async()=>{const t=await http.get(`/analysis/tasks/${created.id}`); if(['completed','failed'].includes(t.status)){clearInterval(timer);running.value=false;await load()}},1800) }
const trendOption=computed(()=>({grid:{left:10,right:15,top:15,bottom:5,containLabel:true},tooltip:{trigger:'axis'},xAxis:{type:'category',data:(result.value.totals?.day||[]).map(i=>i.period.slice(5)),axisLabel:{fontSize:10,color:'#8996a8'},axisLine:{lineStyle:{color:'#e6ebf1'}}},yAxis:{type:'value',axisLabel:{fontSize:10,color:'#8996a8'},splitLine:{lineStyle:{color:'#edf1f6'}}},series:[{type:'bar',data:(result.value.totals?.day||[]).map(i=>i.passenger_flow),barMaxWidth:18,itemStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'#4e8bea'},{offset:1,color:'#8db7f5'}]},borderRadius:[4,4,0,0]}}]}))
const routeOption=computed(()=>({grid:{left:5,right:18,top:3,bottom:0,containLabel:true},tooltip:{trigger:'axis'},xAxis:{type:'value',splitLine:{lineStyle:{color:'#edf1f6'}},axisLabel:{fontSize:9,color:'#8996a8'}},yAxis:{type:'category',inverse:true,data:result.value.routes_top10.map(i=>i.route_name||i.route_id),axisLabel:{fontSize:10,color:'#536176',width:86,overflow:'truncate'}},series:[{type:'bar',data:result.value.routes_top10.map(i=>i.passenger_flow),barWidth:10,itemStyle:{color:'#2e72df',borderRadius:[0,5,5,0]}}]}))
</script>

<template>
  <div class="page" v-loading="loading">
    <PageHeader eyebrow="SPARK SQL" title="离线客流分析" description="使用 Spark DataFrame 与 Spark SQL 计算日/周/月趋势、高峰时段、区域、站点、线路及 OD 流向。">
      <el-button @click="load">刷新结果</el-button><el-button type="primary" :loading="running" @click="start">{{ running?'Spark 正在分析':'运行全量分析' }}</el-button>
    </PageHeader>
    <div class="page-grid grid-3">
      <StatCard label="分析输入" :value="Number(task.input_count||0).toLocaleString()" unit="行" note="Snappy Parquet" :icon="DataAnalysis" />
      <StatCard label="分析输出" :value="Number(task.output_count||0).toLocaleString()" unit="项" note="统计指标与序列" tone="cyan" :icon="Histogram" />
      <StatCard label="计算耗时" :value="task.duration_ms ? (task.duration_ms/1000).toFixed(1) : '—'" unit="秒" note="Spark Local Mode" tone="green" :icon="Timer" />
    </div>
    <PanelCard class="section-gap" title="分析工作台" :subtitle="`结果来自任务 #${task.id||'—'} · ${result.engine||'Spark SQL + DataFrame'}`">
      <template #actions><el-segmented v-model="tab" :options="[{label:'日客流趋势',value:'trend'},{label:'区域热力',value:'heat'},{label:'Top-N OD',value:'od'}]" size="small" /></template>
      <BaseChart v-if="tab==='trend'" :option="trendOption" height="430px" />
      <CityMap v-else-if="tab==='heat'" mode="heat" :regions="result.regions" height="430px" />
      <CityMap v-else mode="od" :od="result.od_top10" height="430px" />
    </PanelCard>
    <div class="page-grid grid-2 section-gap">
      <PanelCard title="热门线路 Top 10" subtitle="固定线路关联统计"><BaseChart :option="routeOption" height="310px" /></PanelCard>
      <PanelCard title="OD 流向排行" subtitle="起点与终点均来自固定站点目录">
        <el-table :data="result.od_top10" height="310"><el-table-column type="index" label="#" width="45" /><el-table-column prop="origin_station" label="起点" /><el-table-column prop="destination_station" label="终点" /><el-table-column label="客流"><template #default="s"><b>{{ Number(s.row.passenger_flow).toLocaleString() }}</b></template></el-table-column></el-table>
      </PanelCard>
    </div>
    <PanelCard class="section-gap" title="任务历史" subtitle="后台异步分析任务与耗时记录" flush>
      <el-table :data="tasks"><el-table-column prop="id" label="任务" width="80" /><el-table-column prop="analysis_type" label="类型" /><el-table-column label="状态"><template #default="s"><el-tag size="small" :type="statusType(s.row.status)">{{statusLabel(s.row.status)}}</el-tag></template></el-table-column><el-table-column label="输入行数"><template #default="s">{{Number(s.row.input_count||0).toLocaleString()}}</template></el-table-column><el-table-column label="耗时"><template #default="s">{{s.row.duration_ms ? `${(s.row.duration_ms/1000).toFixed(1)} 秒`:'—'}}</template></el-table-column><el-table-column prop="error_message" label="错误信息" min-width="220" show-overflow-tooltip /></el-table>
    </PanelCard>
  </div>
</template>
