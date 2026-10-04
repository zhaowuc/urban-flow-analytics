<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { BellFilled, CircleCheck, Memo } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import StatCard from '../components/StatCard.vue'
import http from '../utils/http'

const warnings=ref([]),decisions=ref([]),stations=ref([]),loading=ref(false),levelFilter=ref('')
const stationMap=computed(()=>Object.fromEntries(stations.value.map(s=>[s.station_id,s.station_name])))
const filtered=computed(()=>levelFilter.value?warnings.value.filter(w=>w.level===levelFilter.value):warnings.value)
const count=(level)=>warnings.value.filter(w=>w.level===level).length
const load=async()=>{loading.value=true;try{[warnings.value,decisions.value,stations.value]=await Promise.all([http.get('/warnings?status=active'),http.get('/decisions'),http.get('/catalog/stations')])}finally{loading.value=false}}
onMounted(load)
const generate=async()=>{const r=await http.post('/warnings/generate');ElMessage.success(`已根据预测结果生成 ${r.created_count} 条预警`);load()}
const resolve=async(row)=>{await ElMessageBox.confirm(`确认解除 ${stationMap.value[row.station_id]||row.station_id} 的预警？`,'解除预警',{type:'warning'});await http.put(`/warnings/${row.id}/resolve`);ElMessage.success('预警已解除');load()}
const levelLabel=(l)=>({yellow:'黄色',orange:'橙色',red:'红色',normal:'正常'}[l]||l)
</script>

<template>
  <div class="page" v-loading="loading">
    <PageHeader eyebrow="DECISION SUPPORT" title="预警与决策" description="站点容量统一参与负载率计算；地图与预警页面读取同一状态，避免跨模块不一致。">
      <el-button @click="load">刷新状态</el-button><el-button type="primary" @click="generate">根据最新预测生成预警</el-button>
    </PageHeader>
    <div class="page-grid grid-3">
      <StatCard label="活动预警" :value="warnings.length" unit="条" note="预测 + 实时来源" tone="orange" :icon="BellFilled" />
      <StatCard label="红 / 橙预警" :value="count('red')+count('orange')" unit="条" note="需优先处置" :icon="Memo" />
      <StatCard label="决策建议" :value="decisions.length" unit="项" note="阈值与站点特征驱动" tone="green" :icon="CircleCheck" />
    </div>
    <PanelCard class="section-gap" title="活动预警" subtitle="负载率 = 当前或未来 30 分钟客流 / 站点容量" flush>
      <template #actions><el-segmented v-model="levelFilter" :options="[{label:'全部',value:''},{label:'黄色',value:'yellow'},{label:'橙色',value:'orange'},{label:'红色',value:'red'}]" size="small" /></template>
      <el-table :data="filtered"><el-table-column label="等级" width="85"><template #default="s"><span :class="['level-pill',`level-${s.row.level}`]">{{levelLabel(s.row.level)}}</span></template></el-table-column><el-table-column label="站点" min-width="180"><template #default="s"><b>{{stationMap[s.row.station_id]||s.row.station_id}}</b><small class="station-id">{{s.row.station_id}}</small></template></el-table-column><el-table-column prop="region" label="区域" width="85"/><el-table-column label="预测客流" width="100"><template #default="s">{{Math.round(s.row.predicted_flow)}}</template></el-table-column><el-table-column prop="capacity" label="容量" width="90"/><el-table-column label="负载率" width="160"><template #default="s"><el-progress :percentage="Math.min(100,Math.round(s.row.load_rate*100))" :stroke-width="6" :color="s.row.level==='red'?'#e5484d':s.row.level==='orange'?'#f97316':'#e6a23c'"/></template></el-table-column><el-table-column label="来源" width="95"><template #default="s"><el-tag size="small" effect="plain">{{s.row.source==='realtime'?'实时流':'预测'}}</el-tag></template></el-table-column><el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip/><el-table-column label="操作" width="80"><template #default="s"><el-button link type="primary" @click="resolve(s.row)">解除</el-button></template></el-table-column></el-table>
    </PanelCard>
    <PanelCard class="section-gap" title="决策建议" subtitle="针对预警级别、站点容量与位置自动形成可追溯建议">
      <div class="decision-grid"><article v-for="item in decisions.slice(0,12)" :key="item.id"><div class="decision-top"><span>{{item.category}}</span><small>#{{item.warning_id}}</small></div><h3>{{item.suggestion}}</h3><p>{{item.rationale}}</p></article><div v-if="!decisions.length" class="empty-copy">生成预警后将同步形成决策建议</div></div>
    </PanelCard>
  </div>
</template>

<style scoped>
.station-id{display:block;margin-top:3px;color:#a2adbb;font-size:9px}.decision-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.decision-grid article{padding:16px;border:1px solid var(--line);border-radius:10px;background:#fbfcfe}.decision-top{display:flex;justify-content:space-between;align-items:center}.decision-top span{padding:4px 7px;border-radius:5px;color:#3266b3;background:#edf4ff;font-size:9px;font-weight:700}.decision-top small{color:#a2adbb}.decision-grid h3{margin:13px 0 8px;font-size:12px;line-height:19px}.decision-grid p{margin:0;color:#76859a;font-size:10px;line-height:18px}
</style>
