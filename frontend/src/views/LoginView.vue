<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { Guide, Lock, User } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = ref({ username: 'admin', password: 'admin123' })
const accounts = [
  { label: '管理员', username: 'admin', password: 'admin123' },
  { label: '分析员', username: 'analyst', password: 'analyst123' },
  { label: '访客', username: 'viewer', password: 'viewer123' },
]
const submit = async () => {
  if (!form.value.username || !form.value.password) return
  loading.value = true
  try { await auth.login(form.value); router.replace('/dashboard') } finally { loading.value = false }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <div class="story-grid"></div>
      <div class="story-orb one"></div><div class="story-orb two"></div>
      <div class="story-content">
        <div class="story-brand"><span><Guide /></span><strong>URBAN FLOW</strong></div>
        <div class="story-main">
          <div class="story-kicker">SPARK LOCAL ANALYTICS</div>
          <h1>让城市出行数据<br/>成为清晰的决策依据</h1>
          <p>从统一虚拟城市数据、实时客流到预测预警，在完全离线环境中完成一条可信的数据分析链路。</p>
          <div class="story-features">
            <div><i>01</i><span><b>统一数据底座</b><small>8 区域 · 40 站点 · 12 线路</small></span></div>
            <div><i>02</i><span><b>真实计算引擎</b><small>Spark SQL · Structured Streaming</small></span></div>
            <div><i>03</i><span><b>预测与预警</b><small>ARIMA · Random Forest · GBT</small></span></div>
          </div>
        </div>
        <div class="story-footer">星海示例市 · 内置虚拟交通数据集</div>
      </div>
    </section>
    <section class="login-form-side">
      <div class="login-box">
        <div class="mobile-brand"><Guide /></div>
        <div class="login-eyebrow">WELCOME BACK</div>
        <h2>登录系统</h2>
        <p class="login-help">使用您的系统账户进入城市客流分析控制台</p>
        <el-form size="large" @submit.prevent="submit">
          <label>用户名</label>
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" @keyup.enter="submit" />
          <label>密码</label>
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" @keyup.enter="submit" />
          <el-button type="primary" native-type="submit" :loading="loading" @click="submit">进入分析系统</el-button>
        </el-form>
        <div class="demo-accounts">
          <span>演示账户</span>
          <button v-for="item in accounts" :key="item.username" @click="form = { username: item.username, password: item.password }">{{ item.label }}</button>
        </div>
        <div class="login-notice">本系统完全离线运行，不连接任何在线地图或外部数据服务。</div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page{min-height:100vh;display:grid;grid-template-columns:minmax(570px,1.08fr) minmax(500px,.92fr);background:#fff}.login-story{position:relative;overflow:hidden;color:white;background:linear-gradient(145deg,#07111f,#0d2340 62%,#103b60)}.story-grid{position:absolute;inset:0;opacity:.18;background-image:linear-gradient(rgba(255,255,255,.09) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.09) 1px,transparent 1px);background-size:48px 48px;mask-image:linear-gradient(to bottom,black,transparent)}.story-orb{position:absolute;border-radius:50%;filter:blur(1px)}.story-orb.one{width:440px;height:440px;right:-180px;top:16%;background:radial-gradient(circle,rgba(28,154,226,.23),transparent 68%)}.story-orb.two{width:330px;height:330px;left:-130px;bottom:-90px;background:radial-gradient(circle,rgba(41,104,229,.25),transparent 70%)}.story-content{position:relative;z-index:1;height:100%;min-height:700px;display:flex;flex-direction:column;padding:46px 9% 38px}.story-brand{display:flex;align-items:center;gap:11px}.story-brand>span{width:34px;height:34px;display:grid;place-items:center;border-radius:9px;background:linear-gradient(135deg,#4387ff,#06b6d4)}.story-brand svg{width:19px}.story-brand strong{font-size:12px;letter-spacing:.16em}.story-main{margin:auto 0;max-width:620px}.story-kicker{color:#5fd7ec;font-size:10px;font-weight:750;letter-spacing:.22em}.story-main h1{margin:20px 0 22px;font-size:43px;line-height:1.32;letter-spacing:-.04em;font-weight:680}.story-main>p{max-width:540px;margin:0;color:#a8bad1;font-size:14px;line-height:26px}.story-features{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:52px}.story-features>div{padding:17px 15px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.035);backdrop-filter:blur(8px)}.story-features i{color:#54cce4;font-size:9px;font-style:normal;font-weight:700}.story-features span{display:flex;flex-direction:column;margin-top:13px}.story-features b{font-size:11px}.story-features small{margin-top:6px;color:#7189a5;font-size:8px}.story-footer{color:#607795;font-size:9px;letter-spacing:.08em}.login-form-side{display:grid;place-items:center;padding:70px}.login-box{width:100%;max-width:390px}.mobile-brand{display:none}.login-eyebrow{color:#3974d2;font-size:9px;font-weight:750;letter-spacing:.17em}.login-box h2{margin:10px 0 8px;font-size:28px;letter-spacing:-.035em}.login-help{margin:0 0 35px;color:#8996a8;font-size:12px}.el-form label{display:block;margin:0 0 8px;color:#3f4c60;font-size:11px;font-weight:650}.el-form .el-input{margin-bottom:21px}.el-form .el-button{width:100%;height:44px;margin-top:5px}.demo-accounts{display:flex;align-items:center;gap:7px;margin-top:22px;padding-top:20px;border-top:1px solid #edf0f4}.demo-accounts span{margin-right:auto;color:#9aa5b5;font-size:10px}.demo-accounts button{padding:5px 8px;border:1px solid #e3e8ef;border-radius:6px;color:#64758c;background:#fff;font-size:9px;cursor:pointer}.demo-accounts button:hover{color:#2563eb;border-color:#aec8f8}.login-notice{margin-top:31px;padding:11px 12px;border-radius:8px;color:#73839a;background:#f5f7fa;font-size:9px;line-height:16px;text-align:center}
</style>
