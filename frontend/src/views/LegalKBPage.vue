<template>
  <div class="legal-kb">
    <div class="page-header">
      <h2 class="page-title">法律知识库</h2>
      <button class="btn-add" @click="showAddModal = true">+ 新增法条</button>
    </div>

    <div class="stat-cards">
      <div class="stat-card"><div class="stat-value">{{ clauses.length }}</div><div class="stat-label">总条文数</div></div>
      <div class="stat-card"><div class="stat-value">{{ sources.length }}</div><div class="stat-label">法律来源</div></div>
      <div class="stat-card"><div class="stat-value">{{ stats.by_contract_type ? stats.by_contract_type.purchase || 0 : '-' }}</div><div class="stat-label">采购合同法条</div></div>
      <div class="stat-card"><div class="stat-value">4</div><div class="stat-label">合同类型覆盖</div></div>
    </div>

    <div class="toolbar">
      <input v-model="search" class="search-input" placeholder="搜索法条标题、内容或标签..." />
      <select v-model="filterType" class="filter-select">
        <option value="">全部类型</option><option value="purchase">采购合同</option><option value="service">服务合同</option>
        <option value="lease">租赁合同</option><option value="labor">劳动合同</option>
      </select>
    </div>

    <div class="clause-table-wrap">
      <table class="clause-table">
        <thead><tr><th>条文编号</th><th>标题</th><th>适用</th><th>第一性原理</th><th>权重</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="c in filteredClauses" :key="c.clause_id">
            <td><span class="clause-id-tag">{{ c.clause_id }}</span></td>
            <td>{{ c.title }}</td>
            <td><span v-for="ct in c.contract_types" :key="ct" class="type-tag">{{ typeLabel(ct) }}</span></td>
            <td class="fp-cell">{{ (c.first_principles || '').slice(0, 40) }}{{ (c.first_principles || '').length > 40 ? '...' : '' }}</td>
            <td><span class="weight-badge">{{ c.precedent_weight || 1 }}</span></td>
            <td>
              <button class="btn-sm" @click="viewClause(c)">查看</button>
              <button class="btn-sm btn-danger" @click="deleteClause(c)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add Modal -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal">
        <h3>新增法律条文</h3>
        <div class="form-grid">
          <div class="form-group full"><label>条文编号</label><input v-model="newClause.clause_id" placeholder="如: 民法典第635条" /></div>
          <div class="form-group full"><label>标题</label><input v-model="newClause.title" placeholder="法条标题" /></div>
          <div class="form-group full"><label>条文内容</label><textarea v-model="newClause.content" rows="3" placeholder="条文全文..."></textarea></div>
          <div class="form-group"><label>法律来源</label><input v-model="newClause.source" placeholder="如: 中华人民共和国民法典" /></div>
          <div class="form-group"><label>所属章节</label><input v-model="newClause.chapter" placeholder="如: 合同编" /></div>
          <div class="form-group"><label>适用合同类型</label><select v-model="newClause.contract_types" multiple size="4"><option value="purchase">采购</option><option value="service">服务</option><option value="lease">租赁</option><option value="labor">劳动</option></select></div>
          <div class="form-group"><label>标签（逗号分隔）</label><input v-model="newClause.tagsStr" placeholder="违约责任, 付款条件" /></div>
        </div>
        <div class="modal-btns"><button class="btn-cancel" @click="showAddModal = false">取消</button><button class="btn-save" @click="addClause">保存</button></div>
      </div>
    </div>

    <!-- View Modal -->
    <div v-if="viewingClause" class="modal-overlay" @click.self="viewingClause = null">
      <div class="modal">
        <h3>{{ viewingClause.clause_id }}</h3><h4>{{ viewingClause.title }}</h4>
        <p class="clause-full-text">{{ viewingClause.content }}</p>
        <div class="clause-meta">
          <span>来源: {{ viewingClause.source }}</span><span>章节: {{ viewingClause.chapter }}</span>
          <span>判例权重: {{ viewingClause.precedent_weight || 1 }}</span>
          <span>适用: {{ (viewingClause.contract_types || []).map(t => typeLabel(t)).join(', ') }}</span>
        </div>
        <div class="clause-fp-section" v-if="viewingClause.first_principles">
          <strong>第一性原理</strong>
          <p>{{ viewingClause.first_principles }}</p>
        </div>
        <div class="clause-fp-section" v-if="viewingClause.principles && viewingClause.principles.length">
          <strong>法律原则</strong>
          <p>{{ (typeof viewingClause.principles === 'string' ? JSON.parse(viewingClause.principles) : viewingClause.principles).join('、') }}</p>
        </div>
        <button class="btn-cancel" @click="viewingClause = null">关闭</button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
const API = axios.create({ baseURL: '/api' })

export default {
  name: 'LegalKBPage',
  data() {
    return {
      search: '', filterType: '', showAddModal: false, viewingClause: null,
      newClause: { clause_id: '', title: '', content: '', source: '', chapter: '', contract_types: [], tagsStr: '' },
      clauses: [], stats: {},
    }
  },
  computed: {
    sources() { return [...new Set(this.clauses.map(c => c.source))] },
    filteredClauses() {
      let r = this.clauses
      if (this.filterType) r = r.filter(c => (c.contract_types || []).includes(this.filterType))
      if (this.search) {
        const kw = this.search.toLowerCase()
        r = r.filter(c => (c.title || '').includes(kw) || (c.content || '').includes(kw) || (c.clause_id || '').includes(kw) || (c.tags || []).some(t => t.includes(kw)))
      }
      return r
    },
  },
  async mounted() { await this.fetchAll() },
  methods: {
    typeLabel(ct) { return { purchase: '采购', service: '服务', lease: '租赁', labor: '劳动' }[ct] || ct },
    async fetchAll() {
      try {
        const [clausesRes, statsRes] = await Promise.all([API.get('/legal-kb'), API.get('/legal-kb/stats')])
        this.clauses = clausesRes.data.clauses || []
        this.stats = statsRes.data
      } catch { this.clauses = [] }
    },
    viewClause(c) { this.viewingClause = c },
    async addClause() {
      if (!this.newClause.clause_id || !this.newClause.title) return alert('条文编号和标题必填')
      try {
        await API.post('/legal-kb', {
          clause_id: this.newClause.clause_id, title: this.newClause.title,
          content: this.newClause.content, source: this.newClause.source, chapter: this.newClause.chapter,
          contract_types: this.newClause.contract_types.length ? this.newClause.contract_types : ['purchase'],
          tags: this.newClause.tagsStr ? this.newClause.tagsStr.split(/[,，]/).map(s => s.trim()) : [],
        })
        this.showAddModal = false
        this.newClause = { clause_id: '', title: '', content: '', source: '', chapter: '', contract_types: [], tagsStr: '' }
        await this.fetchAll()
      } catch (e) { alert('保存失败: ' + (e.response?.data?.detail || e.message)) }
    },
    async deleteClause(c) {
      if (!confirm(`确认删除 "${c.clause_id}"？`)) return
      try { await API.delete(`/legal-kb/${encodeURIComponent(c.clause_id)}`); await this.fetchAll() }
      catch (e) { alert('删除失败: ' + (e.response?.data?.detail || e.message)) }
    },
  },
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.btn-add { padding: 8px 20px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer; }
.btn-add:hover { background: #2563eb; }
.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-align: center; }
.stat-value { font-size: 1.8rem; font-weight: 700; color: #1e293b; }
.stat-label { font-size: 0.8rem; color: #64748b; margin-top: 2px; }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.search-input { flex: 1; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; background: #fff; }
.filter-select { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; min-width: 140px; }
.clause-table-wrap { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.clause-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.clause-table th { text-align: left; padding: 10px 12px; background: #f8fafc; color: #64748b; font-weight: 600; border-bottom: 1px solid #e2e8f0; }
.clause-table td { padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }
.clause-id-tag { font-size: 0.75rem; background: #3b82f6; color: #fff; padding: 2px 8px; border-radius: 4px; white-space: nowrap; font-weight: 600; }
.type-tag { font-size: 0.7rem; background: #f1f5f9; color: #475569; padding: 1px 6px; border-radius: 3px; margin-right: 4px; }
.tag-tag { font-size: 0.7rem; background: #fef2f2; color: #b91c1c; padding: 1px 6px; border-radius: 3px; margin-right: 4px; }
.source-cell { font-size: 0.8rem; color: #64748b; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-sm { font-size: 0.75rem; padding: 3px 10px; border: 1px solid #e2e8f0; border-radius: 5px; cursor: pointer; background: #fff; margin-right: 4px; color: #3b82f6; }
.btn-danger { color: #dc2626; border-color: #fecaca; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; padding: 24px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; }
.modal h3 { margin-bottom: 16px; }
.modal h4 { color: #64748b; font-weight: 500; margin-bottom: 12px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-group.full { grid-column: 1 / -1; }
.form-group label { display: block; font-size: 0.8rem; color: #64748b; margin-bottom: 4px; }
.form-group input, .form-group textarea, .form-group select { width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; background: #f8fafc; }
.clause-full-text { font-size: 0.9rem; line-height: 1.8; color: #334155; background: #f8fafc; padding: 16px; border-radius: 8px; margin-bottom: 12px; }
.clause-meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 0.8rem; color: #64748b; margin-bottom: 16px; }
.modal-btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px; }
.btn-save { padding: 8px 24px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
.btn-cancel { padding: 8px 20px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; }
.fp-cell { font-size: 0.78rem; color: #7c3aed; font-style: italic; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.weight-badge { font-size: 0.75rem; background: #faf5ff; color: #7c3aed; padding: 2px 8px; border-radius: 4px; font-weight: 700; }
.clause-fp-section { margin-top: 12px; padding: 10px; background: #faf5ff; border-radius: 6px; }
.clause-fp-section strong { font-size: 0.8rem; color: #7c3aed; display: block; margin-bottom: 4px; }
.clause-fp-section p { font-size: 0.82rem; color: #475569; line-height: 1.6; }
</style>
