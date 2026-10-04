<script setup>
import { onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import http from '../utils/http'

const rows=ref([]),loading=ref(false),filters=ref({username:'',action:''})
const load=async()=>{loading.value=true;try{const q=new URLSearchParams({limit:'300'});if(filters.value.username)q.set('username',filters.value.username);if(filters.value.action)q.set('action',filters.value.action);rows.value=await http.get(`/logs?${q}`)}finally{loading.value=false}}
onMounted(load)
const actionName=(a)=>({login:'用户登录',upload_dataset:'上传数据',preprocess_dataset:'数据清洗',spark_analysis:'Spark 分析',model_train:'模型训练',model_predict:'模型调用',warning_generate:'生成预警',warning_resolve:'解除预警',create_user:'创建用户',update_user:'更新用户',delete_user:'删除用户',update_settings:'更新设置',restore_demo:'恢复数据'}[a]||a)
</script>
<template><div class="page"><PageHeader eyebrow="AUDIT TRAIL" title="操作日志" description="关键登录、数据、分析、模型、预警和系统配置操作均由后端持久化记录。"><el-button @click="load">刷新日志</el-button></PageHeader><PanelCard title="审计记录" subtitle="支持按用户名与操作类型筛选，最新记录优先" flush><div class="log-filter"><el-input v-model="filters.username" placeholder="用户名" clearable :prefix-icon="Search" style="width:180px" @keyup.enter="load"/><el-input v-model="filters.action" placeholder="操作代码" clearable style="width:210px" @keyup.enter="load"/><el-button type="primary" :loading="loading" @click="load">查询</el-button></div><el-table :data="rows" v-loading="loading"><el-table-column prop="id" label="ID" width="65"/><el-table-column label="时间" width="175"><template #default="s"><span class="mono">{{new Date(s.row.created_at).toLocaleString('zh-CN',{hour12:false})}}</span></template></el-table-column><el-table-column prop="username" label="用户" width="105"/><el-table-column label="操作" width="130"><template #default="s"><b>{{actionName(s.row.action)}}</b></template></el-table-column><el-table-column prop="resource" label="资源" width="150" show-overflow-tooltip/><el-table-column prop="detail" label="详情" min-width="250" show-overflow-tooltip/><el-table-column prop="ip_address" label="IP 地址" width="130"/><el-table-column label="结果" width="90"><template #default="s"><span :class="['status-dot',s.row.success?'':'danger']">{{s.row.success?'成功':'失败'}}</span></template></el-table-column></el-table></PanelCard></div></template>
<style scoped>.log-filter{display:flex;gap:10px;padding:0 20px 18px}</style>
