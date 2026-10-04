<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Download, Refresh } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import http from '../utils/http'

const report=ref(null),loading=ref(false)
const generate=async()=>{loading.value=true;try{report.value=await http.post('/reports/generate');ElMessage.success('决策分析报告已生成')}finally{loading.value=false}}
onMounted(generate)
const download=()=>{if(!report.value)return;const token=localStorage.getItem('urban-flow-token');fetch(`/api/reports/download?path=${encodeURIComponent(report.value.path)}`,{headers:{Authorization:`Bearer ${token}`}}).then(r=>r.blob()).then(blob=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=report.value.path.split('/').pop();a.click();URL.revokeObjectURL(a.href)})}
</script>
<template>
  <div class="page">
    <PageHeader eyebrow="REPORT CENTER" title="决策分析报告" description="把最新 Spark 分析、预测评估、容量预警和决策建议汇总为可离线保存的 HTML 报告。"><el-button :icon="Refresh" :loading="loading" @click="generate">重新生成</el-button><el-button type="primary" :icon="Download" :disabled="!report" @click="download">下载报告</el-button></PageHeader>
    <div class="notice-strip"><el-icon><Document/></el-icon>报告明确标识“虚拟示例城市”，不会把内置模拟数据表述为真实城市交通数据。</div>
    <PanelCard class="section-gap report-panel" title="报告预览" :subtitle="report?.path||'正在生成最新报告…'">
      <iframe v-if="report" :srcdoc="report.html" title="决策报告预览"></iframe><div v-else class="empty-copy">正在整理分析结果…</div>
    </PanelCard>
  </div>
</template>
<style scoped>.report-panel :deep(.panel-head){margin-bottom:12px}.report-panel iframe{width:100%;height:680px;border:1px solid var(--line);border-radius:9px;background:white}</style>
