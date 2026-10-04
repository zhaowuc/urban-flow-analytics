<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  Bell, DataAnalysis, DataBoard, Document, Expand, Fold, Guide, Histogram,
  Menu as MenuIcon, Monitor, Operation, Setting, SwitchButton, User, Warning,
} from '@element-plus/icons-vue'

const collapsed = ref(false)
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const menu = [
  { section: '态势中心', items: [
    { path: '/dashboard', label: '综合态势', icon: DataBoard },
    { path: '/realtime', label: '实时客流', icon: Monitor },
    { path: '/warnings', label: '预警与决策', icon: Warning },
  ] },
  { section: '数据智能', items: [
    { path: '/data', label: '数据管理', icon: MenuIcon },
    { path: '/analysis', label: 'Spark 分析', icon: Histogram },
    { path: '/prediction', label: '客流预测', icon: DataAnalysis },
    { path: '/reports', label: '分析报告', icon: Document },
  ] },
  { section: '系统管理', admin: true, items: [
    { path: '/users', label: '用户管理', icon: User },
    { path: '/logs', label: '操作日志', icon: Operation },
    { path: '/settings', label: '系统设置', icon: Setting },
  ] },
]
const visibleMenu = computed(() => menu.filter((group) => !group.admin || auth.isAdmin))
const roleName = computed(() => ({ admin: '系统管理员', analyst: '数据分析员', viewer: '只读访客' }[auth.user?.roles?.[0]?.code || auth.user?.roles?.[0]] || '用户'))
const logout = () => { auth.logout(); router.replace('/login') }
</script>

<template>
  <div :class="['shell', { collapsed }]">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><Guide /></div>
        <div class="brand-copy"><strong>城市客流</strong><span>SPARK ANALYTICS</span></div>
      </div>
      <nav>
        <div v-for="group in visibleMenu" :key="group.section" class="menu-group">
          <div class="menu-caption">{{ group.section }}</div>
          <router-link v-for="item in group.items" :key="item.path" :to="item.path" :class="['menu-item', { active: route.path === item.path }]">
            <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
          </router-link>
        </div>
      </nav>
      <div class="sidebar-foot">
        <div class="engine-state"><i></i><div><strong>Spark Local</strong><span>离线引擎已配置</span></div></div>
      </div>
    </aside>
    <main class="main">
      <header class="topbar">
        <button class="collapse-btn" aria-label="折叠菜单" @click="collapsed = !collapsed"><el-icon><component :is="collapsed ? Expand : Fold" /></el-icon></button>
        <div class="crumb"><span>星海示例市</span><b>/</b><strong>{{ route.meta.title }}</strong></div>
        <div class="topbar-right">
          <div class="offline-chip"><i></i>本地离线模式</div>
          <button class="icon-btn" aria-label="预警中心" @click="router.push('/warnings')"><Bell /></button>
          <el-dropdown trigger="click">
            <div class="user-chip"><div class="avatar">{{ auth.user?.display_name?.slice(0, 1) }}</div><div><strong>{{ auth.user?.display_name }}</strong><span>{{ roleName }}</span></div></div>
            <template #dropdown><el-dropdown-menu><el-dropdown-item :icon="Setting" @click="router.push('/settings')">系统设置</el-dropdown-item><el-dropdown-item divided :icon="SwitchButton" @click="logout">退出登录</el-dropdown-item></el-dropdown-menu></template>
          </el-dropdown>
        </div>
      </header>
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.shell { --side: 224px; min-height:100vh; }.shell.collapsed{--side:76px}
.sidebar { position:fixed; z-index:20; inset:0 auto 0 0; width:var(--side); display:flex; flex-direction:column; overflow:hidden; color:#dfe9f7; background:linear-gradient(180deg,#0b1729,#0a1423); border-right:1px solid rgba(255,255,255,.05); transition:width .25s ease; }
.brand { height:72px; flex:none; display:flex; align-items:center; gap:11px; padding:0 19px; border-bottom:1px solid rgba(255,255,255,.06); }
.brand-mark { width:36px;height:36px;flex:none;display:grid;place-items:center;border-radius:10px;color:white;background:linear-gradient(135deg,#3879ed,#08a7c4);box-shadow:0 8px 22px rgba(31,105,216,.32)}
.brand-mark :deep(svg){width:20px;height:20px}.brand-copy{display:flex;flex-direction:column;white-space:nowrap}.brand-copy strong{font-size:15px;letter-spacing:.04em}.brand-copy span{margin-top:3px;color:#7488a6;font-size:8px;font-weight:700;letter-spacing:.13em}
nav{flex:1;padding:16px 11px;overflow:auto}.menu-group{margin-bottom:20px}.menu-caption{height:25px;padding:0 10px;color:#536985;font-size:9px;font-weight:700;letter-spacing:.12em;white-space:nowrap}.menu-item{position:relative;height:42px;margin:3px 0;display:flex;align-items:center;gap:12px;padding:0 12px;border-radius:8px;color:#91a3bc;text-decoration:none;font-size:12px;font-weight:600;white-space:nowrap;transition:.2s}.menu-item:hover{color:#dce7f6;background:rgba(255,255,255,.035)}.menu-item.active{color:white;background:linear-gradient(90deg,rgba(43,111,232,.28),rgba(43,111,232,.11))}.menu-item.active::before{content:'';position:absolute;left:0;width:3px;height:20px;border-radius:0 3px 3px 0;background:#4b8bff;box-shadow:0 0 12px #3779e9}.menu-item .el-icon{width:18px;font-size:17px}
.sidebar-foot{padding:13px;border-top:1px solid rgba(255,255,255,.06)}.engine-state{display:flex;align-items:center;gap:10px;padding:11px;border-radius:9px;background:rgba(255,255,255,.035);white-space:nowrap}.engine-state i{width:7px;height:7px;flex:none;border-radius:50%;background:#25c98d;box-shadow:0 0 0 4px rgba(37,201,141,.1)}.engine-state div{display:flex;flex-direction:column}.engine-state strong{font-size:10px}.engine-state span{margin-top:3px;color:#6f849e;font-size:9px}
.main{min-height:100vh;margin-left:var(--side);transition:margin-left .25s ease}.topbar{position:sticky;z-index:10;top:0;height:72px;display:flex;align-items:center;padding:0 30px;background:rgba(255,255,255,.94);backdrop-filter:blur(14px);border-bottom:1px solid #e9edf3}.collapse-btn,.icon-btn{width:34px;height:34px;display:grid;place-items:center;border:0;border-radius:8px;color:#62738a;background:transparent;cursor:pointer}.collapse-btn:hover,.icon-btn:hover{background:#f1f4f8;color:#285caa}.crumb{display:flex;align-items:center;gap:9px;margin-left:14px;font-size:11px}.crumb span{color:#9aa6b7}.crumb b{color:#ccd3dc}.crumb strong{color:#41516a}.topbar-right{margin-left:auto;display:flex;align-items:center;gap:15px}.offline-chip{display:flex;align-items:center;gap:7px;padding:6px 10px;border-radius:7px;color:#55708a;background:#f4f7fa;font-size:10px;font-weight:600}.offline-chip i{width:6px;height:6px;border-radius:50%;background:#12a874}.user-chip{display:flex;align-items:center;gap:10px;padding-left:5px;cursor:pointer}.avatar{width:34px;height:34px;display:grid;place-items:center;border-radius:9px;color:#28558f;background:#dfeafe;font-weight:750}.user-chip>div:last-child{display:flex;flex-direction:column}.user-chip strong{font-size:11px}.user-chip span{margin-top:3px;color:#98a4b5;font-size:9px}
.collapsed .brand-copy,.collapsed .menu-caption,.collapsed .menu-item span,.collapsed .engine-state div{display:none}.collapsed .brand{padding:0 20px}.collapsed nav{padding-left:11px;padding-right:11px}.collapsed .menu-item{justify-content:center;padding:0}.collapsed .sidebar-foot{padding:13px 10px}.collapsed .engine-state{justify-content:center}
</style>
