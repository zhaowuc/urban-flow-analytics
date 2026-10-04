<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Coin, Files, Refresh, UploadFilled } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import StatCard from '../components/StatCard.vue'
import http from '../utils/http'

const datasets = ref([])
const tasks = ref([])
const storage = ref({})
const loading = ref(false)
const uploading = ref(false)
const preview = ref(null)
const previewVisible = ref(false)
const fileInput = ref()
let pollTimer
const bytes = (n=0) => n > 1024**3 ? `${(n/1024**3).toFixed(2)} GB` : n > 1024**2 ? `${(n/1024**2).toFixed(2)} MB` : `${(n/1024).toFixed(1)} KB`
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN',{hour12:false}) : '—'
const statusLabel = (s) => ({ ready:'可用',pending:'待处理',queued:'排队中',running:'处理中',processing:'处理中',completed:'已完成',failed:'失败' }[s] || s)
const statusType = (s) => ({ ready:'success',completed:'success',queued:'warning',running:'warning',processing:'warning',failed:'danger' }[s] || 'info')
const totalRows = computed(() => datasets.value.reduce((sum,item)=>sum+(item.row_count||0),0))
const parquetStorage = computed(() => storage.value.locations?.find((item) => item.path === 'data/parquet') || {})
const load = async () => {
  loading.value = true
  try { [datasets.value,tasks.value,storage.value] = await Promise.all([http.get('/datasets'),http.get('/preprocessing/tasks'),http.get('/storage/summary')]) } finally { loading.value=false }
}
onMounted(load)
const chooseFile = () => fileInput.value?.click()
const upload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  const body = new FormData(); body.append('file',file); uploading.value=true
  try { await http.post('/datasets/upload',body,{headers:{'Content-Type':'multipart/form-data'}}); await load(); ElMessage.success('数据集上传成功') } finally { uploading.value=false; event.target.value='' }
}
const showPreview = async (row) => { preview.value=await http.get(`/datasets/${row.id}/preview?limit=30`); previewVisible.value=true }
const preprocess = async (row) => {
  await http.post(`/datasets/${row.id}/preprocess`,{missing_strategy:'fill'}); await load(); ElMessage.success('Spark 清洗任务已提交')
  clearInterval(pollTimer); pollTimer=setInterval(async()=>{ await load(); if(!tasks.value.some(t=>['pending','queued','running','processing'].includes(t.status))) clearInterval(pollTimer) },1800)
}
const restore = async()=>{ await http.post('/datasets/restore-demo'); ElMessage.success('演示数据已恢复'); load() }
</script>

<template>
  <div class="page" v-loading="loading">
    <PageHeader eyebrow="DATA PIPELINE" title="数据管理" description="导入、预览和清洗客流数据，输出供 Spark SQL 与模型共享的 Parquet 分区。">
      <input ref="fileInput" type="file" accept=".csv,.json,.xlsx" hidden @change="upload" />
      <el-button @click="restore">恢复演示数据</el-button><el-button type="primary" :loading="uploading" :icon="UploadFilled" @click="chooseFile">上传数据集</el-button>
    </PageHeader>
    <div class="page-grid grid-3">
      <StatCard label="已登记数据集" :value="datasets.length" unit="个" note="CSV / JSON / XLSX" :icon="Files" />
      <StatCard label="累计数据记录" :value="totalRows.toLocaleString()" unit="行" note="统一实体引用校验" tone="cyan" :icon="Coin" />
      <StatCard label="Parquet 占用" :value="bytes(parquetStorage.size_bytes)" note="Snappy 压缩分区" tone="green" :icon="Refresh" />
    </div>
    <PanelCard class="section-gap" title="数据集目录" subtitle="所有模拟记录均引用固定的 8 区域、40 站点与 12 线路" flush>
      <el-table :data="datasets" style="width:100%">
        <el-table-column prop="id" label="ID" width="65" /><el-table-column prop="name" label="数据集名称" min-width="250" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="100"><template #default="s"><el-tag size="small" effect="plain">{{ s.row.source==='built_in_demo'?'系统演示':'用户上传' }}</el-tag></template></el-table-column>
        <el-table-column prop="file_type" label="格式" width="85"><template #default="s"><span class="file-type">{{ s.row.file_type.toUpperCase() }}</span></template></el-table-column>
        <el-table-column label="大小" width="110"><template #default="s">{{ bytes(s.row.size_bytes) }}</template></el-table-column>
        <el-table-column label="记录数" width="120"><template #default="s">{{ Number(s.row.row_count||0).toLocaleString() }}</template></el-table-column>
        <el-table-column label="处理状态" width="105"><template #default="s"><el-tag size="small" :type="statusType(s.row.processing_status)">{{ statusLabel(s.row.processing_status) }}</el-tag></template></el-table-column>
        <el-table-column label="创建时间" width="170"><template #default="s">{{ formatDate(s.row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" width="180" fixed="right"><template #default="s"><el-button link type="primary" @click="showPreview(s.row)">预览</el-button><el-button link type="primary" :disabled="s.row.processing_status==='processing'" @click="preprocess(s.row)">Spark 清洗</el-button></template></el-table-column>
      </el-table>
    </PanelCard>
    <PanelCard class="section-gap" title="清洗任务" subtitle="真实 Spark DataFrame 去重、缺失处理、实体关联校验与 Parquet 输出" flush>
      <el-table :data="tasks" style="width:100%">
        <el-table-column prop="id" label="任务" width="75" /><el-table-column prop="dataset_id" label="数据集 ID" width="100" />
        <el-table-column label="状态" width="100"><template #default="s"><el-tag size="small" :type="statusType(s.row.status)">{{ statusLabel(s.row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="清洗结果" min-width="360"><template #default="s"><span v-if="s.row.status==='completed'">原始 {{ s.row.report.original_count?.toLocaleString() }} 行 · 清洗后 {{ s.row.report.clean_count?.toLocaleString() }} 行 · 无效 {{ s.row.report.invalid_count?.toLocaleString() }}</span><span v-else class="muted">{{ s.row.error_message || '等待任务执行' }}</span></template></el-table-column>
        <el-table-column label="完成时间" width="180"><template #default="s">{{ formatDate(s.row.completed_at) }}</template></el-table-column>
      </el-table>
    </PanelCard>
    <el-dialog v-model="previewVisible" title="数据预览" width="88%" top="5vh">
      <div v-if="preview" class="preview-meta">展示前 {{ preview.rows?.length }} 行 · 共 {{ Number(preview.total||0).toLocaleString() }} 行</div>
      <el-table v-if="preview" :data="preview.rows" max-height="580" border><el-table-column v-for="col in preview.columns" :key="col" :prop="col" :label="col" min-width="140" show-overflow-tooltip /></el-table>
    </el-dialog>
  </div>
</template>

<style scoped>
.file-type{color:#396dbb;font-size:10px;font-weight:800;letter-spacing:.04em}.muted{color:var(--text-400)}.preview-meta{margin-bottom:12px;color:var(--text-600);font-size:11px}
</style>
