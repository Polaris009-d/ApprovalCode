<template>
  <div class="pending">
    <h2 class="page-title">待审批列表</h2>

    <div class="card" v-if="reports.length === 0">
      <div class="empty">暂无待审批任务，风险评分>0的合同会出现在这里</div>
    </div>

    <div v-else class="report-list">
      <div v-for="r in reports" :key="r.task_id" class="report-item">
        <div class="report-header">
          <span class="report-id">#{{ r.task_id.slice(-12) }}</span>
          <span class="report-type">{{ typeLabel(r.contract_type) }}</span>
          <span :class="['report-risk', (r.risk_level || 'low').toLowerCase()]">{{ r.risk_level || 'LOW' }}</span>
          <span class="report-score">{{ r.risk_score }}分</span>
        </div>
        <div class="report-meta">
          <span>法条引用: {{ r.citations_count }} 条</span>
          <span>{{ formatTime(r.created_at) }}</span>
        </div>
        <div class="report-summary-text" v-if="r.review_summary">{{ r.review_summary }}</div>
        <div class="report-actions">
          <button class="btn-review" @click="goReview(r)">审核</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
const API = axios.create({ baseURL: '/api' })

export default {
  name: 'PendingReviews',
  data() { return { reports: [] } },
  mounted() { this.fetch() },
  methods: {
    async fetch() {
      try {
        const { data } = await API.get('/history', { params: { status: 'pending', limit: 50 } })
        this.reports = data.reports || []
      } catch { this.reports = [] }
    },
    goReview(r) { this.$router.push('/review?task_id=' + r.task_id) },
    typeLabel(ct) { return { purchase: '采购', service: '服务', lease: '租赁', labor: '劳动' }[ct] || ct },
    formatTime(t) { if (!t) return ''; return new Date(t).toLocaleDateString('zh-CN') },
  },
}
</script>

<style scoped>
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; }
.empty { text-align: center; color: #94a3b8; padding: 40px; }
.report-list { display: flex; flex-direction: column; gap: 10px; }
.report-item { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; }
.report-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.report-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.report-id { font-family: monospace; font-size: 0.8rem; color: #64748b; }
.report-type { font-size: 0.9rem; font-weight: 600; color: #1e293b; }
.report-risk { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.report-risk.low { background: #f0fdf4; color: #16a34a; }
.report-risk.medium { background: #fffbeb; color: #d97706; }
.report-risk.high { background: #fef2f2; color: #dc2626; }
.report-risk.critical { background: #7f1d1d; color: #fca5a5; }
.report-score { font-size: 0.85rem; font-weight: 700; color: #dc2626; margin-left: auto; }
.report-meta { display: flex; gap: 16px; font-size: 0.78rem; color: #94a3b8; }
.report-summary-text { margin-top: 6px; font-size: 0.82rem; color: #475569; }
.report-actions { margin-top: 8px; }
.btn-review { padding: 6px 20px; background: #fef3c7; color: #d97706; border: 1px solid #fcd34d; border-radius: 6px; cursor: pointer; font-size: 0.82rem; font-weight: 600; }
.btn-review:hover { background: #fde68a; }
</style>
