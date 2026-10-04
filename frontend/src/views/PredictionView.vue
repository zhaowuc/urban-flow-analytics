<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, DataLine, TrendCharts } from '@element-plus/icons-vue'
import BaseChart from '../components/BaseChart.vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import StatCard from '../components/StatCard.vue'
import http from '../utils/http'

const tasks=ref([]),comparison=ref([]),stations=ref([]),detail=ref(null),loading=ref(false),dialog=ref(false),training=ref(false)
const form=ref({model_type:'gbt',target:'all'})
let timer
const modelName=(v)=>({arima:'ARIMA',random_forest:'Random Forest',gbt:'Gradient-Boosted Trees'}[v]||v)
const load=async()=>{loading.value=true;try{[tasks.value,comparison.value,stations.value]=await Promise.all([http.get('/models/tasks'),http.get('/models/comparison'),http.get('/catalog/stations')]);const best=tasks.value.find(t=>t.status==='completed');if(best)detail.value=await http.get(`/models/tasks/${best.id}?include_result=true`)}finally{loading.value=false}}
onMounted(load)
const train=async()=>{training.value=true;const payload={...form.value,target:form.value.model_type==='arima'?(form.value.target==='all'?'S001':form.value.target):'all',parameters:{}};const t=await http.post('/models/train',payload);dialog.value=false;ElMessage.success(`模型任务 #${t.id} 已提交`);clearInterval(timer);timer=setInterval(async()=>{const current=await http.get(`/models/tasks/${t.id}`);if(['completed','failed'].includes(current.status)){clearInterval(timer);training.value=false;await load();if(current.status==='completed')ElMessage.success(`${modelName(current.model_type)} 训练完成`)}},2200)}
const openDetail=async(row)=>{if(row.status==='completed')detail.value=await http.get(`/models/tasks/${row.id}?include_result=true`)}
const best=computed(()=>comparison.value.length?[...comparison.value].sort((a,b)=>a.rmse-b.rmse)[0]:{})
const chartOption=computed(()=>{const rows=detail.value?.result?.curve||[];return{grid:{left:8,right:15,top:25,bottom:10,containLabel:true},tooltip:{trigger:'axis'},legend:{top:0,right:0,itemWidth:18,textStyle:{fontSize:10,color:'#67768b'}},xAxis:{type:'category',data:rows.map(i=>i.event_time?.slice(5,16).replace('T',' ')),axisLabel:{fontSize:9,color:'#8b98aa',hideOverlap:true},axisLine:{lineStyle:{color:'#e5eaf1'}}},yAxis:{type:'value',splitLine:{lineStyle:{color:'#edf1f6'}},axisLabel:{fontSize:9}},series:[{name:'实际值',type:'line',symbol:'none',data:rows.map(i=>i.actual),lineStyle:{color:'#8a98aa',width:1.5}},{name:'预测值',type:'line',symbol:'none',smooth:.2,data:rows.map(i=>i.predicted),lineStyle:{color:'#2563eb',width:2},areaStyle:{color:'rgba(37,99,235,.06)'}}]}})
</script>

<template>
  <div class="page" v-loading="loading">
    <PageHeader eyebrow="MODEL LAB" title="客流预测模型" description="在同一清洗数据上训练 ARIMA、Spark Random Forest 与 Spark GBT，并用时间有序测试集评估。">
      <el-button @click="load">刷新状态</el-button><el-button type="primary" @click="dialog=true">训练新模型</el-button>
    </PageHeader>
    <div class="page-grid grid-3">
      <StatCard label="已完成模型" :value="comparison.length" unit="类" note="真实训练结果" :icon="Cpu" />
      <StatCard label="当前最佳 RMSE" :value="best.rmse?.toFixed(3)||'—'" :note="modelName(best.model_type)||'等待训练'" tone="cyan" :icon="TrendCharts" />
      <StatCard label="当前最佳 R²" :value="best.r2?.toFixed(3)||'—'" note="时间有序测试集" tone="green" :icon="DataLine" />
    </div>
    <div class="page-grid grid-3 section-gap">
      <section v-for="item in comparison" :key="item.model_type" :class="['model-card','surface',{best:item.task_id===best.task_id}]" @click="openDetail(tasks.find(t=>t.id===item.task_id))">
        <div class="model-head"><div><span>{{modelName(item.model_type)}}</span><small>{{item.model_type==='arima'?'statsmodels':'pyspark.ml'}}</small></div><el-tag v-if="item.task_id===best.task_id" size="small" type="success">当前最佳</el-tag></div>
        <div class="model-metrics"><div><small>MAE</small><b>{{item.mae?.toFixed(3)}}</b></div><div><small>RMSE</small><b>{{item.rmse?.toFixed(3)}}</b></div><div><small>R²</small><b>{{item.r2?.toFixed(3)}}</b></div></div>
      </section>
    </div>
    <PanelCard class="section-gap" :title="detail ? `${modelName(detail.model_type)} · 实际值与预测值` : '预测拟合曲线'" subtitle="点击上方模型卡片切换查看；切分严格按时间先后执行"><BaseChart :option="chartOption" height="380px" /></PanelCard>
    <PanelCard class="section-gap" title="训练任务" subtitle="模型参数、指标与持久化状态" flush>
      <el-table :data="tasks" @row-click="openDetail"><el-table-column prop="id" label="任务" width="70"/><el-table-column label="模型"><template #default="s"><b>{{modelName(s.row.model_type)}}</b></template></el-table-column><el-table-column prop="target" label="预测目标"/><el-table-column label="状态"><template #default="s"><el-tag size="small" :type="s.row.status==='completed'?'success':s.row.status==='failed'?'danger':'warning'">{{s.row.status}}</el-tag></template></el-table-column><el-table-column label="MAE"><template #default="s">{{s.row.metrics.mae?.toFixed(3)||'—'}}</template></el-table-column><el-table-column label="RMSE"><template #default="s">{{s.row.metrics.rmse?.toFixed(3)||'—'}}</template></el-table-column><el-table-column label="R²"><template #default="s">{{s.row.metrics.r2?.toFixed(3)||'—'}}</template></el-table-column><el-table-column prop="error_message" label="错误信息" min-width="180" show-overflow-tooltip /></el-table>
    </PanelCard>
    <el-dialog v-model="dialog" title="训练预测模型" width="470px"><el-form label-position="top"><el-form-item label="模型类型"><el-radio-group v-model="form.model_type"><el-radio-button value="arima">ARIMA</el-radio-button><el-radio-button value="random_forest">Random Forest</el-radio-button><el-radio-button value="gbt">GBT</el-radio-button></el-radio-group></el-form-item><el-form-item v-if="form.model_type==='arima'" label="目标站点"><el-select v-model="form.target" filterable style="width:100%"><el-option v-for="s in stations" :key="s.station_id" :label="`${s.station_id} · ${s.station_name}`" :value="s.station_id"/></el-select></el-form-item><div class="train-note">Spark ML 模型默认面向全部站点；ARIMA 训练单一站点时间序列。训练在后台执行，页面可继续浏览。</div></el-form><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="training" @click="train">开始训练</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.model-card{position:relative;padding:19px 20px;cursor:pointer;transition:.2s}.model-card:hover{transform:translateY(-2px);box-shadow:0 15px 38px rgba(35,65,105,.11)}.model-card.best{border-color:#aad8ca}.model-head{display:flex;align-items:flex-start;justify-content:space-between}.model-head>div{display:flex;flex-direction:column}.model-head span{font-size:13px;font-weight:750}.model-head small{margin-top:5px;color:#9aa6b5;font-size:9px}.model-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:22px}.model-metrics div{display:flex;flex-direction:column}.model-metrics small{color:#9aa5b4;font-size:9px}.model-metrics b{margin-top:6px;font-size:17px;font-variant-numeric:tabular-nums}.train-note{padding:12px;border-radius:8px;color:#65768c;background:#f4f7fa;font-size:10px;line-height:18px}
</style>
