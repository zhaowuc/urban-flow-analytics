import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  {
    path: '/', component: () => import('../layout/AppLayout.vue'), redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '综合态势', eyebrow: 'OVERVIEW' } },
      { path: 'data', name: 'data', component: () => import('../views/DataView.vue'), meta: { title: '数据管理', eyebrow: 'DATA PIPELINE' } },
      { path: 'analysis', name: 'analysis', component: () => import('../views/AnalysisView.vue'), meta: { title: '离线分析', eyebrow: 'SPARK SQL' } },
      { path: 'realtime', name: 'realtime', component: () => import('../views/RealtimeView.vue'), meta: { title: '实时客流', eyebrow: 'STRUCTURED STREAMING' } },
      { path: 'prediction', name: 'prediction', component: () => import('../views/PredictionView.vue'), meta: { title: '客流预测', eyebrow: 'MODEL LAB' } },
      { path: 'warnings', name: 'warnings', component: () => import('../views/WarningView.vue'), meta: { title: '预警与决策', eyebrow: 'DECISION SUPPORT' } },
      { path: 'reports', name: 'reports', component: () => import('../views/ReportView.vue'), meta: { title: '分析报告', eyebrow: 'REPORT CENTER' } },
      { path: 'users', name: 'users', component: () => import('../views/UsersView.vue'), meta: { title: '用户管理', eyebrow: 'ACCESS CONTROL', admin: true } },
      { path: 'logs', name: 'logs', component: () => import('../views/LogsView.vue'), meta: { title: '操作日志', eyebrow: 'AUDIT TRAIL', admin: true } },
      { path: 'settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '系统设置', eyebrow: 'SYSTEM HEALTH' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return auth.token ? '/dashboard' : true
  if (!auth.token) return '/login'
  if (!auth.user) {
    try { await auth.refresh() } catch { return '/login' }
  }
  if (to.meta.admin && !auth.isAdmin) return '/dashboard'
  document.title = `${to.meta.title || '城市客流'} · 星海示例市`
  return true
})

export default router
