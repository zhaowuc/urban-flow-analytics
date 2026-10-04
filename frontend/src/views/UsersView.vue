<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, UserFilled } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import PanelCard from '../components/PanelCard.vue'
import http from '../utils/http'
import { useAuthStore } from '../stores/auth'

const auth=useAuthStore(),users=ref([]),loading=ref(false),dialog=ref(false),editing=ref(null)
const form=ref({username:'',display_name:'',password:'',role_code:'viewer',is_active:true})
const roleLabel=(code)=>({admin:'系统管理员',analyst:'数据分析员',viewer:'只读访客'}[code]||code)
const load=async()=>{loading.value=true;try{users.value=await http.get('/users')}finally{loading.value=false}}
onMounted(load)
const openCreate=()=>{editing.value=null;form.value={username:'',display_name:'',password:'',role_code:'viewer',is_active:true};dialog.value=true}
const openEdit=(row)=>{editing.value=row;form.value={username:row.username,display_name:row.display_name,password:'',role_code:row.roles[0]?.code,is_active:row.is_active};dialog.value=true}
const save=async()=>{if(editing.value){const payload={display_name:form.value.display_name,role_code:form.value.role_code,is_active:form.value.is_active};if(form.value.password)payload.password=form.value.password;await http.put(`/users/${editing.value.id}`,payload)}else{await http.post('/users',form.value)}dialog.value=false;ElMessage.success('用户信息已保存');load()}
const remove=async(row)=>{await ElMessageBox.confirm(`确认删除用户 ${row.username}？`,'删除用户',{type:'warning'});await http.delete(`/users/${row.id}`);ElMessage.success('用户已删除');load()}
</script>
<template>
  <div class="page" v-loading="loading">
    <PageHeader eyebrow="ACCESS CONTROL" title="用户与权限" description="管理员、分析员和访客的权限均由后端 RBAC 强制校验，前端隐藏不等于授权。"><el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button></PageHeader>
    <div class="role-grid"><article><i><UserFilled/></i><div><b>系统管理员</b><span>用户、配置、数据及全部分析权限</span></div></article><article><i><UserFilled/></i><div><b>数据分析员</b><span>数据处理、分析、模型与预警权限</span></div></article><article><i><UserFilled/></i><div><b>只读访客</b><span>看板、统计、预测与报告查看权限</span></div></article></div>
    <PanelCard class="section-gap" title="系统用户" subtitle="默认演示账户可直接用于答辩权限演示" flush>
      <el-table :data="users"><el-table-column prop="id" label="ID" width="65"/><el-table-column label="用户"><template #default="s"><div class="user-cell"><span>{{s.row.display_name.slice(0,1)}}</span><div><b>{{s.row.display_name}}</b><small>@{{s.row.username}}</small></div></div></template></el-table-column><el-table-column label="角色"><template #default="s"><el-tag effect="plain" size="small">{{roleLabel(s.row.roles[0]?.code)}}</el-tag></template></el-table-column><el-table-column label="权限数"><template #default="s">{{s.row.permissions.length}} 项</template></el-table-column><el-table-column label="状态"><template #default="s"><span :class="['status-dot',s.row.is_active?'':'danger']">{{s.row.is_active?'正常':'已停用'}}</span></template></el-table-column><el-table-column label="创建时间"><template #default="s">{{new Date(s.row.created_at).toLocaleString('zh-CN',{hour12:false})}}</template></el-table-column><el-table-column label="操作" width="130"><template #default="s"><el-button link type="primary" @click="openEdit(s.row)">编辑</el-button><el-button link type="danger" :disabled="s.row.id===auth.user?.id" @click="remove(s.row)">删除</el-button></template></el-table-column></el-table>
    </PanelCard>
    <el-dialog v-model="dialog" :title="editing?'编辑用户':'新增用户'" width="460px"><el-form label-position="top"><el-form-item label="用户名"><el-input v-model="form.username" :disabled="!!editing" placeholder="仅支持字母、数字及 _.-"/></el-form-item><el-form-item label="显示名称"><el-input v-model="form.display_name"/></el-form-item><el-form-item :label="editing?'新密码（留空则不修改）':'密码'"><el-input v-model="form.password" type="password" show-password/></el-form-item><el-form-item label="角色"><el-select v-model="form.role_code" style="width:100%"><el-option label="系统管理员" value="admin"/><el-option label="数据分析员" value="analyst"/><el-option label="只读访客" value="viewer"/></el-select></el-form-item><el-form-item v-if="editing" label="账号状态"><el-switch v-model="form.is_active" active-text="正常" inactive-text="停用"/></el-form-item></el-form><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template></el-dialog>
  </div>
</template>
<style scoped>.role-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.role-grid article{display:flex;align-items:center;gap:14px;padding:18px 20px;border:1px solid var(--line);border-radius:12px;background:white;box-shadow:var(--shadow)}.role-grid i{width:36px;height:36px;display:grid;place-items:center;border-radius:9px;color:#3974d2;background:#edf4ff}.role-grid i svg{width:17px}.role-grid div{display:flex;flex-direction:column}.role-grid b{font-size:12px}.role-grid span{margin-top:5px;color:#8795a7;font-size:9px}.user-cell{display:flex;align-items:center;gap:10px}.user-cell>span{width:30px;height:30px;display:grid;place-items:center;border-radius:8px;color:#2b63b8;background:#e8f0fd;font-size:11px;font-weight:700}.user-cell>div{display:flex;flex-direction:column}.user-cell b{font-size:11px}.user-cell small{margin-top:3px;color:#a0aab8;font-size:9px}</style>
