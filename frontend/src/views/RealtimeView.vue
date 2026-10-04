<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { DataLine, Odometer, Stopwatch, Warning } from '@element-plus/icons-vue'
import BaseChart from '../components/BaseChart.vue'
import CityMap from '../components/CityMap.vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import StatCard from '../components/StatCard.vue'
import http from '../utils/http'

const state=ref({state:'stopped',current_total:0,window_5:0,window_10:0,window_15:0,hot_stations:[],hot_routes:[],regions:[],warnings:[],processing_rate:0})
const busy=ref(false); const speed=ref(60); let timer
const stateLabel=computed(()=>({running:'运行中',paused:'已暂停',stopped:'未启动',failed:'异常'}[state.value.state]||state.value.state))
const level=(id)=>state.value.warnings.find(w=>w.station_id===id)?.level||'normal'
const stationData=computed(()=>state.value.hot_stations.map(s=>({...s,current_flow:s.passenger_flow,warning_level:level(s.station_id),load_rate:state.value.warnings.find(w=>w.station_id===s.station_id)?.load_rate||0})))
const refresh=async()=>{ try{state.value=await http.get('/realtime/status')}catch{} }
onMounted(()=>{refresh();timer=setInterval(refresh,2000)});onBeforeUnmount(()=>clearInterval(timer))
const action=async(name)=>{busy.value=true;try{state.value=await http.post(`/realtime/${name}${name==='start'?`?speed=${speed.value}`:''}`);ElMessage.success({start:'实时模拟已启动',pause:'模拟已暂停',resume:'模拟已继续',stop:'实时模拟已停止',reset:'实时环境已重置'}[name])}finally{busy.value=false}}
const barOption=computed(()=>({grid:{left:5,right:18,top:8,bottom:0,containLabel:true},tooltip:{trigger:'axis'},xAxis:{type:'value',splitLine:{lineStyle:{color:'#edf1f6'}},axisLabel:{fontSize:9}},yAxis:{type:'category',inverse:true,data:state.value.hot_stations.slice(0,10).map(i=>i.station_id),axisLabel:{fontSize:10,color:'#66758a'}},series:[{type:'bar',data:state.value.hot_stations.slice(0,10).map(i=>i.passenger_flow),barWidth:9,itemStyle:{color:'#2e72df',borderRadius:[0,5,5,0]}}]}))
</script>

<template>
  <div class="page">
    <PageHeader eyebrow="STRUCTURED STREAMING" title="实时客流监测" description="前端只负责展示；实时数据由固定城市目录生成并经 Spark Structured Streaming 窗口聚合。">
      <el-select v-model="speed" style="width:145px" :disabled="state.state!=='stopped'"><el-option label="演示加速 ×60" :value="60"/><el-option label="演示加速 ×120" :value="120"/></el-select>
      <el-button v-if="state.state==='stopped'||state.state==='failed'" type="primary" :loading="busy" @click="action('start')">启动实时模拟</el-button>
      <el-button v-if="state.state==='running'" :loading="busy" @click="action('pause')">暂停</el-button><el-button v-if="state.state==='paused'" type="primary" :loading="busy" @click="action('resume')">继续</el-button>
      <el-button v-if="['running','paused'].includes(state.state)" type="danger" plain :loading="busy" @click="action('stop')">停止</el-button><el-button :loading="busy" @click="action('reset')">重置</el-button>
    </PageHeader>
    <div :class="['stream-state',state.state]"><span><i></i>{{stateLabel}}</span><b>{{state.engine||'Spark Structured Streaming'}}</b><em>{{state.speed_label}}</em><small>{{state.simulated_time?.replace('T',' ')}}</small><strong v-if="state.error">{{state.error}}</strong></div>
    <div class="page-grid grid-4 section-gap">
      <StatCard label="当前一分钟" :value="Number(state.current_total).toLocaleString()" unit="人次" note="实时流累计" :icon="DataLine" />
      <StatCard label="5 分钟窗口" :value="Number(state.window_5).toLocaleString()" unit="人次" note="事件时间窗口" tone="cyan" :icon="Stopwatch" />
      <StatCard label="15 分钟窗口" :value="Number(state.window_15).toLocaleString()" unit="人次" note="站点负载口径" tone="green" :icon="Odometer" />
      <StatCard label="实时预警" :value="state.warnings.length" unit="条" :note="`${state.processing_rate} rows/s`" tone="orange" :icon="Warning" />
      <PanelCard class="span-3" title="实时客流地图" subtitle="区域热度、站点圆点和预警状态随 Spark 结果更新"><CityMap mode="realtime" :stations="stationData" :regions="state.regions" height="480px" /></PanelCard>
      <PanelCard title="实时站点排行" subtitle="最新 15 分钟事件时间窗口"><BaseChart :option="barOption" height="330px" /><div class="warning-mini"><div v-for="w in state.warnings" :key="w.station_id"><span :class="['level-pill',`level-${w.level}`]">{{w.level}}</span><p>{{w.message}}</p></div><div v-if="!state.warnings.length" class="empty-copy">当前没有拥堵预警</div></div></PanelCard>
    </div>
  </div>
</template>

<style scoped>
.stream-state{min-height:46px;display:flex;align-items:center;gap:18px;padding:0 16px;border:1px solid #e3e9f1;border-radius:10px;background:#fff;color:#77869a;font-size:10px}.stream-state span{display:flex;align-items:center;gap:8px;color:#52627a;font-weight:750}.stream-state span i{width:8px;height:8px;border-radius:50%;background:#98a5b6}.stream-state.running span i{background:#12a874;box-shadow:0 0 0 5px rgba(18,168,116,.1);animation:pulse 1.8s infinite}.stream-state.paused span i{background:#e6a23c}.stream-state.failed span i{background:#e5484d}.stream-state b{font-weight:650}.stream-state em{padding:4px 7px;border-radius:5px;background:#f2f5f9;font-style:normal}.stream-state small{margin-left:auto}.stream-state strong{color:#c53a40}@keyframes pulse{50%{box-shadow:0 0 0 8px rgba(18,168,116,0)}}.warning-mini{margin-top:12px;border-top:1px solid var(--line)}.warning-mini>div{display:flex;align-items:flex-start;gap:8px;padding:10px 0;border-bottom:1px solid var(--line)}.warning-mini p{margin:1px 0 0;color:#69788c;font-size:9px;line-height:15px}
</style>
