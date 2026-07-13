<template>
  <div class="dashboard">
    <h2 class="page-title">工作台</h2>

    <div class="stat-cards">
      <div class="stat-card clickable warn" @click="$router.push('/pending')">
        <div class="stat-value">{{ stats.pending }}</div>
        <div class="stat-label">待审批</div>
      </div>
      <div class="stat-card highlight">
        <div class="stat-value">{{ stats.autoRate }}%</div>
        <div class="stat-label">AI 自动通过率</div>
      </div>
      <div class="stat-card warn">
        <div class="stat-value">{{ stats.rejected }}</div>
        <div class="stat-label">已驳回</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总审批数</div>
      </div>
    </div>

    <div class="dash-card">
      <h3>最近通过</h3>
      <div v-if="recentApproved.length === 0" class="empty">暂无已审批记录</div>
      <div class="flow-item" v-for="r in recentApproved" :key="r.task_id">
        <div class="flow-left">
          <span class="flow-type">{{ typeLabel(r.contract_type) }}</span>
          <span class="flow-name">#{{ r.task_id ? r.task_id.slice(-12) : '' }}</span>
        </div>
        <div class="flow-right">
          <span class="flow-status done">已通过</span>
          <span class="flow-agent">{{ r.risk_level || 'LOW' }}</span>
        </div>
      </div>
    </div>

    <div class="quick-actions">
      <router-link to="/review" class="action-card primary">
        <span>发起合同审查</span>
      </router-link>
      <router-link to="/legal-kb" class="action-card">
        <span>法律知识库</span>
      </router-link>
      <router-link to="/agents" class="action-card">
        <span>Agent 监控</span>
      </router-link>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
const API = axios.create({ baseURL: '/api' })

export default {
  name: 'Dashboard',
  data() {
    return { stats: { pending: 0, autoRate: 0, rejected: 0, total: 0 }, recentApproved: [] }
  },
  async mounted() {
    try {
      const [healthRes, historyRes] = await Promise.all([
        API.get('/health'),
        API.get('/history', { params: { limit: 10 } }),
      ])
      const h = healthRes.data
      this.stats = {
        pending: h.tasks_pending || 0,
        autoRate: h.auto_rate || 0,
        rejected: h.tasks_rejected || 0,
        total: h.tasks_total || 0,
      }
      this.recentApproved = (historyRes.data.reports || []).filter(r => r.status === 'approved').slice(0, 5)
    } catch { this.stats = { autoRate: 0, rejected: 0, total: 0 } }
  },
  methods: {
    typeLabel(ct) { return { purchase: '采购', service: '服务', lease: '租赁', labor: '劳动' }[ct] || ct },
  },
}
</script>

<style scoped>
.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; text-align: center; }
.stat-card.highlight { border-color: #3b82f6; background: #eff6ff; }
.stat-card.warn { border-color: #f59e0b; background: #fffbeb; }
.stat-card.clickable { cursor: pointer; transition: all 0.15s; }
.stat-card.clickable:hover { border-color: #3b82f6; box-shadow: 0 2px 8px rgba(59,130,246,0.15); }
.stat-value { font-size: 2rem; font-weight: 700; color: #1e293b; }
.stat-label { font-size: 0.85rem; color: #64748b; margin-top: 4px; }
.dash-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 24px; }
.dash-card h3 { font-size: 1rem; margin-bottom: 12px; color: #1e293b; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; }
.empty { color: #94a3b8; padding: 20px; text-align: center; font-size: 0.85rem; }
.flow-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f8fafc; }
.flow-left { display: flex; flex-direction: column; }
.flow-type { font-size: 0.75rem; color: #94a3b8; }
.flow-name { font-size: 0.9rem; color: #1e293b; }
.flow-right { display: flex; align-items: center; gap: 8px; }
.flow-status { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.flow-status.done { background: #f0fdf4; color: #16a34a; }
.flow-agent { font-size: 0.75rem; color: #64748b; }
.quick-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.action-card { display: flex; align-items: center; justify-content: center; padding: 24px; border-radius: 10px; text-decoration: none; border: 1px solid #e2e8f0; background: #fff; transition: all 0.2s; color: #1e293b; font-weight: 600; }
.action-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateY(-2px); }
.action-card.primary { background: #eff6ff; border-color: #3b82f6; color: #2563eb; }
</style>
