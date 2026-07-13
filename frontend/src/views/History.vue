<template>
  <div class="history">
    <h2 class="page-title">审查记录</h2>

    <div class="toolbar">
      <select v-model="filterType" class="filter-select">
        <option value="">全部类型</option>
        <option value="purchase">采购合同</option>
        <option value="service">服务合同</option>
        <option value="lease">租赁合同</option>
        <option value="labor">劳动合同</option>
      </select>
      <button class="btn-refresh" @click="fetchHistory">刷新</button>
    </div>

    <div class="card" v-if="reports.length === 0">
      <div class="empty">暂无审查记录，请先发起智能审查</div>
    </div>

    <div v-else class="report-list">
      <div v-for="r in reports" :key="r.task_id" class="report-item">
        <div class="report-header">
          <span class="report-id">#{{ r.task_id.slice(-12) }}</span>
          <span class="report-type">{{ typeLabel(r.contract_type) }}</span>
          <span :class="['report-status', r.status]">{{ statusLabel(r.status) }}</span>
          <span :class="['report-risk', (r.risk_level || 'low').toLowerCase()]">{{ r.risk_level || 'LOW' }}</span>
        </div>
        <div class="report-meta">
          <span>风险评分: {{ r.risk_score }}</span>
          <span>法条引用: {{ r.citations_count }} 条</span>
          <span>不一致字段: {{ r.mismatch_count }} 处</span>
          <span>{{ formatTime(r.created_at) }}</span>
        </div>
        <div class="report-summary-text" v-if="r.review_summary">{{ r.review_summary }}</div>
        <div class="report-actions">
          <button class="btn-detail" @click="viewDetail(r)">详情</button>
        </div>
      </div>

      <!-- 详情弹窗 -->
      <div v-if="detail" class="modal-overlay" @click.self="detail = null">
        <div class="modal-detail">
          <h3>审查详情</h3>
          <div class="detail-grid">
            <div class="detail-item"><label>任务编号</label><span>{{ detail.task_id }}</span></div>
            <div class="detail-item"><label>合同类型</label><span>{{ typeLabel(detail.contract_type) }}</span></div>
            <div class="detail-item"><label>状态</label><span :class="['report-status', detail.status]">{{ statusLabel(detail.status) }}</span></div>
            <div class="detail-item"><label>风险评分</label><span>{{ detail.risk_score }} / {{ detail.risk_level || 'LOW' }}</span></div>
            <div class="detail-item"><label>法条引用</label><span>{{ detail.citations_count }} 条</span></div>
            <div class="detail-item"><label>不一致字段</label><span>{{ detail.mismatch_count }} 处</span></div>
            <div class="detail-item"><label>创建时间</label><span>{{ formatTime(detail.created_at) }}</span></div>
          </div>
          <div class="detail-section" v-if="detail.review_summary">
            <label>审查摘要</label>
            <p>{{ detail.review_summary }}</p>
          </div>
          <div class="detail-section">
            <label>合同信息</label>
            <div class="detail-grid">
              <div class="detail-item"><label>合同类型</label><span>{{ typeLabel(detail.contract_type) }}</span></div>
              <div class="detail-item"><label>合同金额</label><span>{{ detail.report_data?.form_amount || '-' }}</span></div>
              <div class="detail-item"><label>甲方</label><span>{{ detail.report_data?.form_party_a || '-' }}</span></div>
              <div class="detail-item"><label>乙方</label><span>{{ detail.report_data?.form_party_b || '-' }}</span></div>
              <div class="detail-item"><label>签订日期</label><span>{{ detail.report_data?.form_date || '-' }}</span></div>
              <div class="detail-item"><label>付款周期</label><span>{{ detail.report_data?.form_payment_period || '-' }}</span></div>
            </div>
          </div>
          <div class="detail-section" v-if="detail.report_data">
            <!-- 风险模式或字段对比：自动判断数据类型 -->
            <div v-if="detail.report_data.mismatch_fields && detail.report_data.mismatch_fields.length">
              <label>{{ detail.report_data.mismatch_fields[0].pattern_id ? '风险模式' : '字段比对' }}</label>
              <table v-if="!detail.report_data.mismatch_fields[0].pattern_id" class="compare-table">
                <thead><tr><th>字段</th><th>用户填写</th><th>OCR识别</th></tr></thead>
                <tbody>
                  <tr v-for="m in detail.report_data.mismatch_fields" :key="m.field">
                    <td>{{ m.field }}</td><td>{{ m.user_input || '-' }}</td><td>{{ m.extracted || '-' }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-else class="risk-pattern-list">
                <div v-for="m in detail.report_data.mismatch_fields" :key="m.pattern_id" class="risk-pattern-item">
                  <span :class="'severity-badge ' + (m.severity || 'medium').toLowerCase()">{{ m.severity || 'MEDIUM' }}</span>
                  <div>
                    <strong>{{ m.pattern_id }}</strong>
                    <p>{{ m.explanation || '' }}</p>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="detail.report_data.citations && detail.report_data.citations.length" style="margin-top:12px">
              <label>引用法条</label>
              <div v-for="c in detail.report_data.citations" :key="c.id" class="detail-clause">
                <span class="clause-id">{{ c.id }}</span> <strong>{{ c.title }}</strong>
                <p class="clause-content">{{ c.content }}</p>
              </div>
            </div>
            <div v-if="detail.report_data.risk_breakdown && detail.report_data.risk_breakdown.length" style="margin-top:12px">
              <label>风险评分明细</label>
              <div v-for="b in detail.report_data.risk_breakdown" :key="b.name" class="breakdown-row">
                <span>{{ b.name }}</span>
                <span :class="b.score > 0 ? 'score-up' : 'score-zero'">{{ b.score > 0 ? '+' : '' }}{{ b.score }}分</span>
                <span class="breakdown-reason">{{ b.detail }}</span>
              </div>
            </div>
            <div v-if="detail.report_data.risk_advice" style="margin-top:12px">
              <label>审批建议</label>
              <p>{{ detail.report_data.risk_advice }}</p>
            </div>
          </div>
          <button class="btn-cancel" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
const API = axios.create({ baseURL: '/api' })

export default {
  name: 'HistoryPage',
  data() {
    return { reports: [], filterType: '', filterStatus: '', detail: null }
  },
  mounted() { this.applyRouteFilter(); this.fetchHistory() },
  watch: { '$route'() { this.applyRouteFilter(); this.fetchHistory() } },
  methods: {
    applyRouteFilter() {
      const q = this.$route.query || {}
      this.filterType = q.contract_type || ''
      this.filterStatus = q.status || ''
    },
    async fetchHistory() {
      try {
        const params = {}
        if (this.filterType) params.contract_type = this.filterType
        if (this.filterStatus) params.status = this.filterStatus
        const { data } = await API.get('/history', { params })
        this.reports = data.reports || []
      } catch { this.reports = [] }
    },
    typeLabel(ct) { return { purchase: '采购', service: '服务', lease: '租赁', labor: '劳动' }[ct] || ct },
    statusLabel(s) { return { approved: '已通过', rejected: '已驳回', pending: '待审批' }[s] || s },
    formatTime(t) { if (!t) return ''; return new Date(t).toLocaleDateString('zh-CN') },
    viewDetail(r) { this.detail = r },
  },
}
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.filter-select { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; min-width: 140px; }
.btn-refresh { padding: 8px 20px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; }
.empty { text-align: center; color: #94a3b8; padding: 40px; }
.report-list { display: flex; flex-direction: column; gap: 10px; }
.report-item { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; transition: box-shadow 0.15s; }
.report-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.report-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.report-id { font-family: monospace; font-size: 0.8rem; color: #64748b; }
.report-type { font-size: 0.9rem; font-weight: 600; color: #1e293b; }
.report-status { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.report-status.approved { background: #f0fdf4; color: #16a34a; }
.report-status.rejected { background: #fef2f2; color: #dc2626; }
.report-status.pending { background: #fffbeb; color: #d97706; }
.report-risk { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; margin-left: auto; }
.report-risk.low { background: #f0fdf4; color: #16a34a; }
.report-risk.medium { background: #fffbeb; color: #d97706; }
.report-risk.high { background: #fef2f2; color: #dc2626; }
.report-meta { display: flex; gap: 16px; font-size: 0.78rem; color: #94a3b8; }
.report-summary-text { margin-top: 6px; font-size: 0.82rem; color: #475569; }
.report-actions { margin-top: 8px; }
.btn-detail { padding: 4px 16px; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; border-radius: 6px; cursor: pointer; font-size: 0.8rem; }
.btn-detail:hover { background: #dbeafe; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.6); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal-detail { background: #fff; border-radius: 12px; padding: 24px 28px; max-width: 560px; width: 90%; max-height: 80vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.modal-detail h3 { font-size: 1.1rem; color: #1e293b; margin-bottom: 16px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.detail-item label { display: block; font-size: 0.72rem; color: #94a3b8; margin-bottom: 2px; }
.detail-item span { font-size: 0.88rem; color: #1e293b; font-weight: 500; }
.detail-section { margin-bottom: 14px; }
.detail-section label { font-size: 0.8rem; color: #64748b; font-weight: 600; display: block; margin-bottom: 6px; }
.detail-section p { font-size: 0.85rem; color: #475569; line-height: 1.5; }
.detail-clause { font-size: 0.82rem; color: #475569; padding: 4px 0; }
.clause-id { font-size: 0.7rem; background: #3b82f6; color: #fff; padding: 1px 6px; border-radius: 3px; margin-right: 4px; }
.btn-cancel { padding: 8px 24px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; font-size: 0.9rem; color: #64748b; margin-top: 12px; }
.btn-cancel:hover { background: #f8fafc; }
.compare-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 6px; }
.compare-table th { text-align: left; padding: 6px 8px; background: #f8fafc; color: #64748b; }
.compare-table td { padding: 6px 8px; border-bottom: 1px solid #f1f5f9; }
.risk-pattern-list { display: flex; flex-direction: column; gap: 10px; }
.risk-pattern-item { display: flex; gap: 10px; align-items: flex-start; padding: 8px; background: #f8fafc; border-radius: 6px; }
.risk-pattern-item strong { font-size: 0.82rem; color: #1e293b; }
.risk-pattern-item p { font-size: 0.78rem; color: #64748b; margin: 2px 0 0; }
.severity-badge { font-size: 0.65rem; padding: 2px 6px; border-radius: 3px; font-weight: 700; white-space: nowrap; }
.severity-badge.critical { background: #fff1f2; color: #be123c; border: 1px solid #fda4af; }
.severity-badge.high { background: #fef2f2; color: #dc2626; }
.severity-badge.medium { background: #fffbeb; color: #d97706; }
.severity-badge.low { background: #f0fdf4; color: #16a34a; }
.clause-content { font-size: 0.78rem; color: #64748b; margin: 2px 0 0 0; line-height: 1.4; }
.breakdown-row { display: flex; gap: 8px; align-items: center; padding: 4px 0; font-size: 0.82rem; }
.breakdown-reason { font-size: 0.76rem; color: #94a3b8; margin-left: auto; }
.score-up { color: #dc2626; font-weight: 600; }
.score-zero { color: #64748b; }
</style>
