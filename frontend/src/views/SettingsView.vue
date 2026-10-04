<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Cpu, FolderOpened, Setting } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import http from '../utils/http'
import { useAuthStore } from '../stores/auth'

const auth=useAuthStore(),health=ref({}),values=ref({}),loading=ref(false)
const items=computed(()=>[{key:'web',label:'Web 服务',icon:CircleCheck,...health.value.web},{key:'database',label:'SQLite 数据库',icon:FolderOpened,...health.value.database},{key:'spark',label:'Spark Local 引擎',icon:Cpu,...health.value.spark},{key:'models',label:'预测模型',icon:Setting,...health.value.models},{key:'data_directory',label:'数据目录',icon:FolderOpened,...health.value.data_directory}])
const load=async()=>{loading.value=true;try{const [healthData,settingsData]=await Promise.all([http.get('/health'),http.get('/settings')]);health.value=healthData;values.value={...settingsData,'warning.yellow':Number(settingsData['warning.yellow']),'warning.orange':Number(settingsData['warning.orange']),'warning.red':Number(settingsData['warning.red']),'demo.speed':Number(settingsData['demo.speed'])}}finally{loading.value=false}}
onMounted(load)
const save=async()=>{values.value=await http.put('/settings',{values:{'warning.yellow':String(values.value['warning.yellow']),'warning.orange':String(values.value['warning.orange']),'warning.red':String(values.value['warning.red']),'demo.speed':String(values.value['demo.speed'])}});ElMessage.success('系统参数已保存')}
</script>
<template>
  <div class="page" v-loading="loading"><PageHeader eyebrow="SYSTEM HEALTH" title="系统设置与健康" description="检查 Web、SQLite、Spark、模型和数据目录状态，并维护容量预警阈值。"><el-button @click="load">重新检测</el-button></PageHeader>
    <div class="health-grid"><article v-for="item in items" :key="item.key" class="surface"><i><component :is="item.icon"/></i><div><b>{{item.label}}</b><span>{{item.path||item.master||item.bind||`${item.count??''}`}}</span></div><em :class="['status-dot',item.ok?'':'danger']">{{item.status}}</em></article></div>
    <div class="page-grid grid-2 section-gap"><PanelCard title="预警阈值" subtitle="系统统一根据负载率分级，设置后对地图和预警模块同时生效"><el-form label-position="top"><el-form-item label="黄色预警阈值"><el-input-number v-model="values['warning.yellow']" :min="0.1" :max="2" :step="0.05" :precision="2"/><span class="input-suffix">负载率</span></el-form-item><el-form-item label="橙色预警阈值"><el-input-number v-model="values['warning.orange']" :min="0.1" :max="2" :step="0.05" :precision="2"/><span class="input-suffix">负载率</span></el-form-item><el-form-item label="红色预警阈值"><el-input-number v-model="values['warning.red']" :min="0.1" :max="2" :step="0.05" :precision="2"/><span class="input-suffix">负载率</span></el-form-item><el-button v-if="auth.isAdmin" type="primary" @click="save">保存参数</el-button></el-form></PanelCard><PanelCard title="部署信息" subtitle="绿色离线发行版的实际运行配置"><dl class="deploy-info"><div><dt>部署模式</dt><dd>{{health.deployment_mode}}</dd></div><div><dt>服务地址</dt><dd>127.0.0.1（仅本机访问）</dd></div><div><dt>Java 运行时</dt><dd>项目内置 JRE 17</dd></div><div><dt>Python 运行时</dt><dd>项目内置 Python 3.11</dd></div><div><dt>地图服务</dt><dd>assets/maps/demo_city.json</dd></div><div><dt>外部依赖</dt><dd>无在线 GIS / 无外部中间件</dd></div></dl></PanelCard></div>
    <div class="notice-strip section-gap">当前系统使用内置模拟城市交通数据集进行功能验证，通过本地 GeoJSON、虚拟站点及线路数据完成客流分析、OD 流向、预测与预警。实际应用时可通过替换城市 GeoJSON、站点、线路和真实客流数据迁移到实际城市环境。</div>
  </div>
</template>
<style scoped>.health-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.health-grid article{display:grid;grid-template-columns:34px 1fr;align-items:center;gap:10px;padding:16px}.health-grid article>i{width:34px;height:34px;display:grid;place-items:center;border-radius:9px;color:#316dcc;background:#edf4ff}.health-grid svg{width:16px}.health-grid article>div{display:flex;flex-direction:column;min-width:0}.health-grid b{font-size:11px}.health-grid span{margin-top:4px;color:#99a5b4;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.health-grid em{grid-column:1/3;margin-top:8px;font-style:normal}.input-suffix{margin-left:10px;color:#8794a7;font-size:10px}.deploy-info{margin:0}.deploy-info div{display:flex;justify-content:space-between;padding:13px 0;border-bottom:1px solid var(--line);font-size:11px}.deploy-info dt{color:#8b98aa}.deploy-info dd{margin:0;color:#34445b;font-weight:600}</style>
