<template>
  <div class="review-page">
    <h2 class="page-title">智能合同审查</h2>

    <div class="step-nav">
      <div :class="['step-item', { active: currentStep >= 0, done: currentStep > 0 }]"><span class="step-num">1</span> 发起审批</div>
      <div class="step-line"></div>
      <div :class="['step-item', { active: currentStep >= 1, done: currentStep > 1 }]"><span class="step-num">2</span> 智能审查</div>
      <div class="step-line"></div>
      <div :class="['step-item', { active: currentStep >= 2 }]"><span class="step-num">3</span> 审查结果</div>
    </div>

    <div class="review-layout">
      <div class="review-main">

        <!-- ═══════════ Step 1: 发起审批 ═══════════ -->
        <div v-show="currentStep === 0" class="step-panel">
          <!-- 上传区 -->
          <div class="card">
            <h3>合同上传（自动识别）</h3>
            <div class="upload-zone" @click="$refs.fileInput.click()" @dragover.prevent @drop.prevent="onDrop">
              <input ref="fileInput" type="file" accept=".pdf,.jpg,.jpeg,.png" @change="onFileSelect" style="display:none" />
              <div v-if="!uploadedFile"><span class="upload-label">点击上传 PDF / 扫描件 / 图片</span><span class="upload-sub">百度云 OCR 自动识别并回填表单</span></div>
              <div v-else-if="ocrLoading"><span class="upload-label">正在 OCR 识别中...</span><span class="upload-sub">百度云通用文字识别 + DeepSeek 字段提取</span></div>
              <div v-else><span class="upload-ok">已识别完成</span><span>{{ uploadedFile }}</span></div>
            </div>
          </div>

          <!-- 合同图片 + OCR 蓝框标注 -->
          <div class="card" v-if="ocrImage">
            <h3>合同原文 — OCR 识别字段（蓝色标注）</h3>
            <div class="image-viewer" ref="imageViewer">
              <img :src="'data:image/png;base64,' + ocrImage" class="contract-image" @load="onImageLoad" />
              <div v-for="(box, i) in ocrBoxes" :key="'ocr'+i"
                class="annotation-box match"
                :style="{ top: box.top + 'px', left: box.left + 'px', width: box.width + 'px', height: box.height + 'px' }"
                :title="box.field + ': ' + box.value">
                <span class="annotation-label">{{ box.field }}</span>
              </div>
            </div>
          </div>

          <!-- 表单 — OCR 自动回填，可手动修改 -->
          <div class="card">
            <h3>合同信息（OCR 自动回填，可手动修改）</h3>
            <div class="form-grid">
              <div class="form-group"><label>合同类型</label>
                <select v-model="form.contract_type">
                  <option value="purchase">采购合同</option><option value="service">服务合同</option>
                  <option value="lease">租赁合同</option><option value="labor">劳动合同</option>
                </select>
              </div>
              <div class="form-group">
                <label>合同金额 <span v-if="ocrFields.amount && form.amount !== ocrFields.amount" class="hint-warn">（OCR: {{ ocrFields.amount }}）</span></label>
                <input v-model="form.amount" :class="{ 'input-mismatch': ocrFields.amount && form.amount !== ocrFields.amount }" placeholder="1,000,000" />
              </div>
              <div class="form-group">
                <label>甲方 <span v-if="ocrFields.party_a && form.party_a !== ocrFields.party_a" class="hint-warn">（OCR: {{ ocrFields.party_a }}）</span></label>
                <input v-model="form.party_a" :class="{ 'input-mismatch': ocrFields.party_a && form.party_a !== ocrFields.party_a }" placeholder="甲方公司全称" />
              </div>
              <div class="form-group">
                <label>乙方 <span v-if="ocrFields.party_b && form.party_b !== ocrFields.party_b" class="hint-warn">（OCR: {{ ocrFields.party_b }}）</span></label>
                <input v-model="form.party_b" :class="{ 'input-mismatch': ocrFields.party_b && form.party_b !== ocrFields.party_b }" placeholder="乙方公司全称" />
              </div>
              <div class="form-group">
                <label>签订日期 <span v-if="ocrFields.date && form.date !== ocrFields.date" class="hint-warn">（OCR: {{ ocrFields.date }}）</span></label>
                <input v-model="form.date" :class="{ 'input-mismatch': ocrFields.date && form.date !== ocrFields.date }" type="text" placeholder="YYYY-MM-DD" />
              </div>
              <div class="form-group">
                <label>付款周期 <span v-if="ocrFields.payment_period && form.payment_period !== ocrFields.payment_period" class="hint-warn">（OCR: {{ ocrFields.payment_period }}）</span></label>
                <input v-model="form.payment_period" :class="{ 'input-mismatch': ocrFields.payment_period && form.payment_period !== ocrFields.payment_period }" placeholder="如: 30天" />
              </div>
            </div>
            <div v-if="hasMismatches" class="mismatch-banner">
              您修改了 {{ mismatchCount }} 个字段，与 OCR 识别结果不一致。提交后将在审查阶段标红显示。
            </div>
          </div>

          <button class="btn-next" @click="startReview" :disabled="submitting || !uploadedFile">
            {{ submitting ? '审查中...' : '提交智能审查' }}
          </button>
        </div>

        <!-- ═══════════ Step 2: 智能审查 ═══════════ -->
        <div v-show="currentStep === 1" class="step-panel">
          <!-- 合同图片 + 不一致红框 / 一致绿框 -->
          <div class="card" v-if="ocrImage">
            <h3>合同原文 — 字段比对标注</h3>
            <div class="image-viewer" ref="imageViewer2">
              <img :src="'data:image/png;base64,' + ocrImage" class="contract-image" />
              <div v-for="(box, i) in reviewBoxes" :key="'rv'+i"
                :class="['annotation-box', box.mismatch ? 'mismatch' : 'match']"
                :style="{ top: box.top + 'px', left: box.left + 'px', width: box.width + 'px', height: box.height + 'px' }"
                :title="box.field + ': OCR=' + box.ocrVal + ' 用户=' + box.userVal">
                <span class="annotation-label">{{ box.field }}{{ box.mismatch ? ' 不一致' : '' }}</span>
              </div>
            </div>
            <div class="annotation-legend">
              <span class="legend-item"><span class="legend-dot mismatch"></span> 不一致（已标红）</span>
              <span class="legend-item"><span class="legend-dot match"></span> 一致</span>
            </div>
          </div>

          <div class="card">
            <h3>字段交叉验证</h3>
            <table class="compare-table">
              <thead><tr><th>字段</th><th>用户填写</th><th>OCR 识别</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="row in fieldCompare" :key="row.field">
                  <td>{{ row.field }}</td><td>{{ row.user }}</td><td>{{ row.extracted }}</td>
                  <td><span :class="['match-badge', row.match ? 'ok' : 'warn']">{{ row.match ? '一致' : '不一致' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="card" v-if="matchedClauses.length">
            <h3>法条匹配 (含第一性原理)</h3>
            <div class="clause-list">
              <div v-for="c in matchedClauses" :key="c.id" class="clause-item">
                <span class="clause-id">{{ c.id }}</span>
                <div class="clause-body">
                  <strong>{{ c.title }}</strong>
                  <p>{{ c.content }}</p>
                  <p v-if="c.first_principles" class="clause-fp">第一性原理: {{ c.first_principles }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- 对抗性辩论 -->
          <div class="card" v-if="debates.length">
            <h3>对抗性辩论 (原告 vs 被告 vs 法官)</h3>
            <div v-for="(d, di) in debates.slice(0, 3)" :key="'db'+di" class="debate-block">
              <div class="debate-clause-header">{{ d.clause?.id || '' }} {{ d.clause?.title || '' }}</div>
              <div class="debate-round" v-if="d.plaintiff?.length">
                <span class="round-label plaintiff">原告指控</span>
                <span v-for="(p, pi) in d.plaintiff" :key="'p'+pi" class="debate-point">{{ p.claim || p }}</span>
              </div>
              <div class="debate-round" v-if="d.defendant?.length">
                <span class="round-label defendant">被告辩护</span>
                <span v-for="(df, di2) in d.defendant" :key="'d'+di2" class="debate-point">{{ df.point || df }}</span>
              </div>
              <div class="debate-verdict" v-if="d.verdict">
                <span :class="'verdict-badge ' + (d.verdict.risk_finding || 'low').toLowerCase()">{{ d.verdict.risk_finding || 'LOW' }}</span>
                <span>{{ d.verdict.verdict || d.verdict.final_advice || '' }}</span>
              </div>
            </div>
          </div>
          <div class="reviewing-hint">智能审查中... 已完成 {{ agentSteps.length }} 步推理{{ matchedClauses.length ? '，匹配 ' + matchedClauses.length + ' 条法条' : '' }}</div>
        </div>

        <!-- ═══════════ Step 3: 审查结果 ═══════════ -->
        <div v-show="currentStep === 2" class="step-panel">
          <!-- 风险评分卡 -->
          <div class="card risk-card" :class="riskLevel">
            <h3>审查结论</h3>
            <div class="risk-summary">
              <div :class="['risk-score-circle', riskLevel]">
                <span class="risk-num">{{ riskScore }}</span>
                <span class="risk-label">/ 100</span>
              </div>
              <div class="risk-detail">
                <span :class="['risk-level-badge', riskLevel]">{{ riskLevelText }}</span>
                <p class="risk-advice">{{ riskAdvice || riskSummary }}</p>
              </div>
            </div>
          </div>

          <!-- 评分明细 -->
          <div class="card" v-if="riskBreakdown.length">
            <h3>评分明细</h3>
            <div class="breakdown-list">
              <div v-for="(item, i) in riskBreakdown" :key="i" class="breakdown-item">
                <div class="breakdown-header">
                  <span class="breakdown-name">{{ item.name }}</span>
                  <span :class="['breakdown-score', item.score > 0 ? 'up' : item.score < 0 ? 'down' : 'zero']">
                    {{ item.score > 0 ? '+' : '' }}{{ item.score }} 分
                  </span>
                </div>
                <div class="breakdown-bar-wrap">
                  <div class="breakdown-bar-bg">
                    <div class="breakdown-bar-fill" :style="{ width: barWidth(item) }" :class="barClass(item)"></div>
                  </div>
                  <span class="breakdown-max">上限 {{ item.max > 0 ? item.max : '-' }} 分</span>
                </div>
                <p class="breakdown-detail">{{ item.detail }}</p>
              </div>
            </div>
            <div class="breakdown-total">
              <span>综合评分</span>
              <span class="total-score">{{ riskScore }} / 100</span>
            </div>
          </div>

          <!-- 风险项 -->
          <div class="card" v-if="risks.length">
            <h3>风险项</h3>
            <div class="risk-item" v-for="r in risks" :key="r.id">
              <span :class="['risk-dot', r.level]"></span>
              <div><strong>{{ r.title }}</strong><p>{{ r.desc }}</p></div>
              <span :class="['risk-tag', r.level]">{{ r.levelText }}</span>
            </div>
          </div>

          <!-- 法条引用 (Step 3 也显示) -->
          <div class="card" v-if="matchedClauses.length">
            <h3>法条匹配</h3>
            <div class="clause-list">
              <div v-for="c in matchedClauses" :key="c.id" class="clause-item">
                <span class="clause-id">{{ c.id }}</span>
                <div class="clause-body"><strong>{{ c.title }}</strong><p>{{ c.content }}</p></div>
              </div>
            </div>
          </div>

          <div v-if="riskScore > 0" class="btn-row">
            <button class="btn-pass" @click="showConfirm = 'approve'">审批通过</button>
            <button class="btn-reject" @click="showConfirm = 'reject'">驳回修改</button>
          </div>
          <div v-else class="auto-approved">风险评分 {{ riskScore }} 分 — 已自动通过，可点击左侧"审查记录"查看。</div>
          <div v-if="riskScore > 0" class="needs-review-banner">风险评分 {{ riskScore }} 分 — 需要人工复核，请点击下方按钮确认。</div>
        </div>

        <!-- 确认弹窗 -->
        <div v-if="showConfirm" class="modal-overlay" @click.self="showConfirm = null">
          <div class="modal-confirm">
            <h3>{{ showConfirm === 'approve' ? '确认审批通过' : '确认驳回' }}</h3>
            <p>{{ showConfirm === 'approve' ? '确认该审批通过后将记录为已通过状态。' : '驳回后该审批将标记为已驳回，需重新提交。' }}</p>
            <div class="modal-btns">
              <button class="btn-cancel" @click="showConfirm = null">取消</button>
              <button :class="showConfirm === 'approve' ? 'btn-pass' : 'btn-reject'" @click="doConfirm">{{ showConfirm === 'approve' ? '确认通过' : '确认驳回' }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Agent 侧边栏 (Step 1 隐藏) -->
      <div class="agent-sidebar" v-show="currentStep >= 1">
        <h3>Agent 实时推理</h3>
        <div class="agent-steps">
          <div v-for="(step, i) in agentSteps" :key="i" :class="['agent-step', step.type]">
            <span :class="['agent-step-icon', step.agentType || 'master']">{{ agentInitial(step) }}</span>
            <div class="agent-step-body">
              <div class="agent-step-header">
                <span class="agent-step-type">{{ step.type }}</span>
                <span class="agent-step-agent">{{ step.agent }}</span>
              </div>
              <p>{{ step.content }}</p>
              <span class="agent-step-time">{{ step.time }}</span>
            </div>
          </div>
        </div>
        <div v-if="matchedClauses.length" class="agent-info-box"><strong>引用法条</strong><span>{{ matchedClauses.length }} 条</span></div>
        <div v-if="riskScore > 0" class="agent-info-box warn-box"><strong>风险评估</strong><span>{{ riskScore }} / {{ riskLevelText }}</span></div>
      </div>
    </div>
  </div>
</template>

<script>
const FIELD_LABELS = {
  amount: '合同金额', party_a: '甲方', party_b: '乙方', date: '签订日期',
  payment_period: '付款周期', subject: '标的物',
}

export default {
  name: 'ReviewPage',
  mounted() {
    const tid = this.$route.query.task_id
    if (tid) this.loadExistingReport(tid)
  },
  data() {
    return {
      currentStep: 0, submitting: false, ocrLoading: false,
      uploadedFile: null, fileBlob: null,
      form: { contract_type: 'purchase', amount: '', party_a: '', party_b: '', date: '', payment_period: '' },
      // OCR results from /api/upload/ocr
      ocrImage: '', ocrPositions: [], ocrFields: {}, ocrFullText: '',
      // For step 1 display (blue boxes)
      ocrBoxes: [],
      // For step 2 display (blue/green vs red)
      reviewBoxes: [],
      // Review data
      fieldCompare: [], matchedClauses: [],
      riskScore: 0, riskLevel: 'low', riskLevelText: '低风险', riskSummary: '',
      riskAdvice: '', riskBreakdown: [],
      risks: [], agentSteps: [], taskId: null, showConfirm: null, debates: [],
      financialFindings: [], negotiationOptions: [],
      imageScale: 1,
    }
  },
  computed: {
    hasMismatches() { return this.mismatchCount > 0 },
    mismatchCount() {
      const f = this.form, o = this.ocrFields
      let n = 0
      for (const k of Object.keys(FIELD_LABELS)) { if (o[k] && f[k] && String(f[k]).trim() !== String(o[k]).trim()) n++ }
      return n
    },
    mismatchFields() {
      const f = this.form, o = this.ocrFields, result = []
      for (const k of Object.keys(FIELD_LABELS)) {
        result.push({ field: k, ocrVal: o[k] || '', userVal: f[k] || '', mismatch: o[k] && f[k] && String(f[k]).trim() !== String(o[k]).trim() })
      }
      return result
    },
  },
  methods: {
    async loadExistingReport(taskId) {
      try {
        const resp = await fetch('/api/history?limit=50')
        const data = await resp.json()
        const report = (data.reports || []).find(r => r.task_id === taskId)
        if (!report) return
        this.taskId = report.task_id
        const rd = report.report_data || {}
        this.riskScore = report.risk_score || rd.risk_score || 0
        this.riskLevel = (report.risk_level || rd.risk_level || 'low').toLowerCase()
        this.riskLevelText = report.risk_level || rd.risk_level || '低风险'
        this.riskSummary = report.review_summary || ''
        this.riskAdvice = rd.risk_advice || ''
        this.riskBreakdown = rd.risk_breakdown || []
        this.matchedClauses = (rd.citations || []).map(c => ({ id: c.id, title: c.title, content: c.content }))
        this.ocrImage = rd._ocr_image || ''
        const mf = rd.mismatch_fields || []
        this.fieldCompare = mf.map(m => ({ field: m.field, user: m.user_input || '', extracted: m.extracted || '', match: false }))
        this.risks = mf.map((m, i) => {
          if (m.pattern_id) return { id: i+1, title: m.pattern_id, desc: m.explanation || '', level: (m.severity || 'MEDIUM').toLowerCase(), levelText: m.severity || '中风险' }
          return { id: i+1, title: (m.field || '未知') + ' 不一致', desc: '用户填写"' + (m.user_input || '') + '"，合同识别为"' + (m.extracted || '') + '"', level: 'mid', levelText: '中风险' }
        })
        this.currentStep = 2
      } catch { this.currentStep = 0 }
    },
    agentInitial(step) {
      const a = step.agent || ''
      if (a.includes('Master') || a.includes('master')) return 'M'
      if (a.includes('Extract') || a.includes('extract')) return 'E'
      if (a.includes('Comply') || a.includes('comply')) return 'C'
      if (a.includes('Risk') || a.includes('risk')) return 'R'
      return 'A'
    },
    onImageLoad(e) {
      const naturalW = e.target.naturalWidth
      const displayW = e.target.clientWidth
      this.imageScale = displayW / Math.max(naturalW, 1)
      this._updateBoxes()
    },
    _updateBoxes() {
      if (!this.ocrPositions.length || !this.imageScale) return
      const scale = this.imageScale
      this.ocrBoxes = this.ocrPositions.map(p => ({
        field: p.field, value: p.value,
        top: Math.round(p.top * scale), left: Math.round(p.left * scale),
        width: Math.max(Math.round(p.width * scale), 60), height: Math.max(Math.round(p.height * scale), 22),
      }))
      this.reviewBoxes = this.ocrPositions.map(p => {
        const userVal = this.form[p.field] || ''
        const mm = userVal && p.value && String(userVal).trim() !== String(p.value).trim()
        return {
          field: p.field, ocrVal: p.value, userVal,
          top: Math.round(p.top * scale), left: Math.round(p.left * scale),
          width: Math.max(Math.round(p.width * scale), 60), height: Math.max(Math.round(p.height * scale), 22),
          mismatch: mm,
        }
      })
    },

    // ═══ 文件选择 → 自动 OCR ═══
    onFileSelect(e) { const f = e.target.files[0]; if (f) this._processFile(f) },
    onDrop(e) { const f = e.dataTransfer.files[0]; if (f) this._processFile(f) },
    async _processFile(file) {
      this.uploadedFile = file.name; this.fileBlob = file; this.ocrLoading = true
      try {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('contract_type', this.form.contract_type)
        const resp = await fetch('/api/upload/ocr', { method: 'POST', body: fd })
        const data = await resp.json()
        this.ocrImage = data.image_base64 || ''
        this.ocrPositions = data.positions || []
        this.ocrFields = data.fields || {}
        this.ocrFullText = data.full_text || ''
        // 自动回填表单
        const f = data.fields || {}
        if (f.amount) this.form.amount = f.amount
        if (f.party_a) this.form.party_a = f.party_a
        if (f.party_b) this.form.party_b = f.party_b
        if (f.date) this.form.date = f.date
        if (f.payment_period) this.form.payment_period = f.payment_period
        if (f.contract_type) this.form.contract_type = f.contract_type
        // 延迟等图片渲染后计算标注框
        this.$nextTick(() => { setTimeout(() => { this.imageScale = 1; this._updateBoxes() }, 300) })
      } catch (e) {
        alert('OCR 识别失败: ' + e.message)
      } finally { this.ocrLoading = false }
    },

    // ═══ 提交审查 ═══
    async startReview() {
      this.submitting = true; this.currentStep = 1
      this._updateBoxes()  // 用最新 form 值更新 review boxes

      // 构建字段比对表
      const mf = this.mismatchFields
      this.fieldCompare = mf.filter(x => x.ocrVal).map(x => ({
        field: FIELD_LABELS[x.field] || x.field,
        user: x.userVal, extracted: x.ocrVal, match: !x.mismatch,
      }))

      const fd = new FormData()
      fd.append('file', this.fileBlob)
      fd.append('contract_type', this.form.contract_type)
      fd.append('user_input', JSON.stringify({
        amount: this.form.amount, party_a: this.form.party_a,
        party_b: this.form.party_b, date: this.form.date, payment_period: this.form.payment_period,
        _ocr_data: { fields: this.ocrFields, positions: this.ocrPositions, image_base64: this.ocrImage, full_text: this.ocrFullText },
      }))

      try {
        const response = await fetch('/api/approval/start', { method: 'POST', body: fd })
        const reader = response.body.getReader(); const decoder = new TextDecoder()
        while (true) {
          const { done, value } = await reader.read(); if (done) break
          for (const line of decoder.decode(value, { stream: true }).split('\n')) {
            if (line.startsWith('data: ')) { try { this.handleSSE(JSON.parse(line.slice(6))) } catch {} }
          }
        }
      } catch (e) {
        this.agentSteps.push({ type: 'ERROR', agent: 'System', agentType: 'system', content: '请求失败: ' + e.message, time: new Date().toLocaleTimeString() })
      } finally { this.submitting = false }
    },
    handleSSE(ev) {
      if (ev.type === 'start') {
        this.taskId = ev.task_id || null
        return
      }
      if (ev.type === 'step' && ev.data) {
        const d = ev.data
        let content = d.content || ''
        try { const j = JSON.parse(content); if (j.tool) content = '调用工具: ' + j.tool } catch {}
        this.agentSteps.push({
          type: (d.step_type || 'act').toUpperCase(),
          agent: d.agent_id || 'Unknown', agentType: this._agentType(d.agent_id),
          content: content.slice(0, 120), time: new Date().toLocaleTimeString(),
        })
        // 实时提取法条：检测 search_law 工具的结果
        if (d.tool_result && d.tool_result.data && d.tool_result.data.clauses) {
          d.tool_result.data.clauses.forEach(c => {
            if (!this.matchedClauses.find(m => m.id === c.id)) {
              this.matchedClauses.push({ id: c.id, title: c.title || '', content: c.content || '' })
            }
          })
        }
      } else if (ev.type === 'report' && ev.data) {
        const r = ev.data
        if (r._ocr_image) this.ocrImage = r._ocr_image
        if (r._ocr_positions) { this.ocrPositions = r._ocr_positions; this._updateBoxes() }
        if (r.mismatch_fields) {
          const mfNew = r.mismatch_fields.map(m => ({
            field: m.field, user: m.user_input || '', extracted: m.extracted || '', match: false,
          }))
          const mismatchNames = new Set(r.mismatch_fields.map(m => m.field))
          for (const [k, v] of Object.entries(r._ocr_fields || {})) {
            if (!mismatchNames.has(k) && this.form[k]) {
              mfNew.push({ field: k, user: this.form[k] || '', extracted: v || '', match: true })
            }
          }
          this.fieldCompare = mfNew
        }
        // 法条引用
        const citations = r.citations || (r.report_data || {}).citations || []
        if (citations.length) {
          this.matchedClauses = citations.map(c => ({ id: c.id || '', title: c.title || '', content: c.content || '', first_principles: c.first_principles || '' }))
        if (r.verified_arguments || r.debates) this.debates = r.debates || r.verified_arguments || []
        }
        this.riskScore = r.risk_score || 0
        this.riskLevel = (r.risk_level || 'low').toLowerCase()
        this.riskLevelText = r.risk_level || '低风险'
        this.riskSummary = r.review_summary || ''
        this.riskAdvice = r.risk_advice || ''
        this.riskBreakdown = r.risk_breakdown || []
        // 智能判断：pattern_id → 风险模式；field → 字段对比
        const rawRisks = r.mismatch_fields || r.risk_patterns || []
        this.risks = rawRisks.map((m, i) => {
          if (m.pattern_id) {
            return { id: i + 1, title: m.pattern_id, desc: m.explanation || '', level: (m.severity || 'MEDIUM').toLowerCase(), levelText: m.severity || '中风险' }
          }
          return { id: i + 1, title: (m.field || '未知') + ' 不一致', desc: '用户填写"' + (m.user_input || '') + '"，合同识别为"' + (m.extracted || '') + '"', level: 'mid', levelText: '中风险' }
        })
        this.currentStep = 2
        // 只有风险分数为0才自动通过，否则需要人工复核
        if (this.riskScore === 0 && this.taskId) {
          fetch(`/api/approval/${this.taskId}/approve`, { method: 'POST' })
        }
      }
    },
    _agentType(id) {
      if (!id) return ''
      if (id.includes('master')) return 'master'
      if (id.includes('extract')) return 'extract'
      if (id.includes('comply')) return 'comply'
      if (id.includes('risk')) return 'risk'
      return ''
    },
    barWidth(item) {
      if (item.max > 0) return Math.min(Math.abs(item.score) / item.max * 100, 100) + '%'
      return Math.min(Math.abs(item.score) / 10 * 100, 100) + '%'
    },
    barClass(item) {
      if (item.score > 0) return 'bar-up'
      if (item.score < 0) return 'bar-down'
      return 'bar-zero'
    },
    async doConfirm() {
      if (!this.taskId || !this.showConfirm) return
      const action = this.showConfirm
      this.showConfirm = null
      try {
        await fetch(`/api/approval/${this.taskId}/${action === 'approve' ? 'approve' : 'reject'}`, { method: 'POST' })
        window.location.href = '/#/history'
      } catch { window.location.href = '/#/history' }
    },
  },
}
</script>

<style scoped>
.step-nav { display: flex; align-items: center; margin-bottom: 20px; }
.step-item { display: flex; align-items: center; gap: 8px; padding: 10px 20px; background: #f1f5f9; border-radius: 8px; font-size: 0.9rem; color: #94a3b8; }
.step-item.active { background: #eff6ff; color: #2563eb; font-weight: 600; }
.step-item.done { background: #f0fdf4; color: #16a34a; }
.step-num { width: 24px; height: 24px; border-radius: 50%; background: #e2e8f0; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; }
.step-item.active .step-num { background: #3b82f6; color: #fff; }
.step-item.done .step-num { background: #22c55e; color: #fff; }
.step-line { flex: 1; height: 2px; background: #e2e8f0; max-width: 60px; }
.review-layout { display: grid; grid-template-columns: 1fr 320px; gap: 20px; }
.review-main { min-width: 0; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.card h3 { font-size: 0.95rem; margin-bottom: 12px; color: #1e293b; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-group label { display: block; font-size: 0.78rem; color: #64748b; margin-bottom: 4px; }
.form-group input, .form-group select { width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; background: #f8fafc; }
.form-group input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); outline: none; }
.input-mismatch { border-color: #f59e0b !important; background: #fffbeb !important; }
.hint-warn { font-size: 0.7rem; color: #d97706; font-weight: 500; }
.mismatch-banner { margin-top: 12px; padding: 10px 14px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; font-size: 0.82rem; color: #b91c1c; }

.upload-zone { border: 2px dashed #cbd5e1; border-radius: 10px; padding: 28px; text-align: center; cursor: pointer; transition: border-color 0.2s; }
.upload-zone:hover { border-color: #3b82f6; }
.upload-label { font-size: 0.95rem; font-weight: 600; display: block; }
.upload-sub { font-size: 0.75rem; color: #94a3b8; display: block; margin-top: 4px; }
.upload-ok { font-size: 0.85rem; font-weight: 600; color: #16a34a; display: block; }

/* Image viewer with annotations */
.image-viewer { position: relative; display: inline-block; max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.contract-image { display: block; max-width: 100%; height: auto; }
.annotation-box { position: absolute; border: 2px solid #3b82f6; background: rgba(59,130,246,0.10); border-radius: 3px; pointer-events: none; display: flex; align-items: flex-end; }
.annotation-box.mismatch { border-color: #ef4444; background: rgba(239,68,68,0.16); box-shadow: 0 0 8px rgba(239,68,68,0.35); }
.annotation-box.match { border-color: #3b82f6; background: rgba(59,130,246,0.08); }
.annotation-label { font-size: 0.58rem; color: #fff; padding: 1px 5px; white-space: nowrap; border-radius: 2px; font-weight: 600; }
.annotation-box.mismatch .annotation-label { background: #ef4444; }
.annotation-box.match .annotation-label { background: #3b82f6; }
.annotation-legend { display: flex; gap: 16px; margin-top: 8px; font-size: 0.78rem; }
.legend-item { display: flex; align-items: center; gap: 6px; color: #64748b; }
.legend-dot { width: 14px; height: 4px; border-radius: 2px; }
.legend-dot.mismatch { background: #ef4444; }
.legend-dot.match { background: #3b82f6; }

.btn-next { width: 100%; padding: 12px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; margin-top: 8px; }
.btn-next:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-next:hover:not(:disabled) { background: #2563eb; }

.compare-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.compare-table th { text-align: left; padding: 8px 10px; background: #f8fafc; color: #64748b; font-weight: 600; }
.compare-table td { padding: 8px 10px; border-bottom: 1px solid #f1f5f9; }
.match-badge { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.match-badge.ok { background: #f0fdf4; color: #16a34a; }
.match-badge.warn { background: #fef2f2; color: #dc2626; }
.clause-list { display: flex; flex-direction: column; gap: 10px; }
.clause-item { display: flex; gap: 12px; padding: 10px; background: #f8fafc; border-radius: 8px; }
.clause-id { font-size: 0.7rem; background: #3b82f6; color: #fff; padding: 2px 8px; border-radius: 4px; white-space: nowrap; font-weight: 600; }
.clause-body strong { font-size: 0.85rem; color: #1e293b; }
.clause-body p { font-size: 0.8rem; color: #64748b; margin: 4px 0; line-height: 1.4; }

.risk-card { border-left: 4px solid #e2e8f0; }
.risk-card.low { border-left-color: #22c55e; } .risk-card.mid { border-left-color: #f59e0b; } .risk-card.high { border-left-color: #ef4444; } .risk-card.critical { border-left-color: #be123c; border-left-width: 5px; }
.risk-summary { display: flex; align-items: center; gap: 16px; }
.risk-score-circle { width: 80px; height: 80px; border-radius: 50%; border: 4px solid #f59e0b; display: flex; flex-direction: column; align-items: center; justify-content: center; flex-shrink: 0; }
.risk-num { font-size: 1.8rem; font-weight: 700; color: #d97706; }
.risk-label { font-size: 0.7rem; color: #64748b; }
.risk-level-badge { font-size: 0.8rem; padding: 4px 12px; border-radius: 6px; font-weight: 700; }
.risk-level-badge.low { background: #f0fdf4; color: #16a34a; } .risk-level-badge.mid { background: #fffbeb; color: #d97706; } .risk-level-badge.high { background: #fef2f2; color: #dc2626; } .risk-level-badge.critical { background: #fff1f2; color: #be123c; border: 1px solid #fda4af; }
.risk-item { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.risk-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
.risk-dot.high { background: #ef4444; } .risk-dot.mid { background: #f59e0b; } .risk-dot.low { background: #fbbf24; } .risk-dot.critical { background: #be123c; }
.risk-item strong { font-size: 0.85rem; color: #1e293b; }
.risk-item p { font-size: 0.8rem; color: #64748b; margin: 2px 0 0; }
.risk-tag { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.risk-tag.high { background: #fef2f2; color: #dc2626; } .risk-tag.mid { background: #fffbeb; color: #d97706; } .risk-tag.critical { background: #fff1f2; color: #be123c; font-weight: 700; }
.btn-row { display: flex; gap: 12px; margin-top: 16px; }
.btn-pass, .btn-reject { flex: 1; padding: 12px; border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; }
.btn-pass { background: #16a34a; color: #fff; } .btn-reject { background: #fff; color: #dc2626; border: 2px solid #dc2626; }

/* Agent sidebar */
.agent-sidebar { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; height: fit-content; position: sticky; top: 20px; }
.agent-sidebar h3 { font-size: 0.95rem; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #f1f5f9; }
.agent-step { display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f8fafc; }
.agent-step-icon { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; font-weight: 800; color: #fff; flex-shrink: 0; }
.agent-step-icon.master { background: #7c3aed; } .agent-step-icon.extract { background: #2563eb; }
.agent-step-icon.comply { background: #059669; } .agent-step-icon.risk { background: #d97706; } .agent-step-icon.system { background: #64748b; }
.agent-step-body { flex: 1; min-width: 0; }
.agent-step-header { display: flex; gap: 6px; align-items: center; margin-bottom: 2px; }
.agent-step-type { font-size: 0.6rem; padding: 1px 5px; border-radius: 3px; font-weight: 700; }
.agent-step.THINK .agent-step-type { background: #ede9fe; color: #7c3aed; }
.agent-step.ACT .agent-step-type { background: #fef3c7; color: #d97706; }
.agent-step.OBSERVE .agent-step-type { background: #d1fae5; color: #059669; }
.agent-step.ERROR .agent-step-type { background: #fef2f2; color: #dc2626; }
.agent-step-agent { font-size: 0.65rem; color: #64748b; margin-left: auto; }
.agent-step-body p { font-size: 0.76rem; color: #475569; margin: 3px 0; line-height: 1.4; }
.agent-step-time { font-size: 0.6rem; color: #94a3b8; }
.agent-info-box { display: flex; justify-content: space-between; padding: 10px; margin-top: 12px; background: #f0f9ff; border-radius: 8px; font-size: 0.8rem; }
.agent-info-box.warn-box { background: #fffbeb; }

/* Risk breakdown */
.breakdown-list { display: flex; flex-direction: column; gap: 14px; }
.breakdown-item { border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; }
.breakdown-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.breakdown-name { font-size: 0.88rem; font-weight: 600; color: #1e293b; }
.breakdown-score { font-size: 0.85rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.breakdown-score.up { background: #fef2f2; color: #dc2626; }
.breakdown-score.down { background: #f0fdf4; color: #16a34a; }
.breakdown-score.zero { background: #f1f5f9; color: #64748b; }
.breakdown-bar-wrap { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.breakdown-bar-bg { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; }
.breakdown-bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }
.bar-up { background: #ef4444; }
.bar-down { background: #22c55e; }
.bar-zero { background: #94a3b8; width: 4px !important; }
.breakdown-max { font-size: 0.7rem; color: #94a3b8; white-space: nowrap; }
.breakdown-detail { font-size: 0.78rem; color: #64748b; margin: 0; }
.breakdown-total { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; padding-top: 12px; border-top: 2px solid #e2e8f0; font-size: 0.95rem; font-weight: 700; color: #1e293b; }
.total-score { font-size: 1.2rem; color: #dc2626; }
.risk-score-circle.low { border-color: #22c55e; }
.risk-score-circle.mid { border-color: #f59e0b; }
.risk-score-circle.high { border-color: #ef4444; }
.risk-score-circle.low .risk-num { color: #16a34a; }
.risk-score-circle.mid .risk-num { color: #d97706; }
.risk-score-circle.high .risk-num { color: #dc2626; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.6); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal-confirm { background: #fff; border-radius: 12px; padding: 28px 32px; max-width: 400px; width: 90%; text-align: center; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.modal-confirm h3 { font-size: 1.1rem; color: #1e293b; margin-bottom: 8px; }
.modal-confirm p { font-size: 0.88rem; color: #64748b; margin-bottom: 20px; }
.modal-btns { display: flex; gap: 10px; justify-content: center; }
.btn-cancel { padding: 8px 24px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; font-size: 0.9rem; color: #64748b; }
.btn-cancel:hover { background: #f8fafc; }
.auto-approved { padding: 16px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; text-align: center; color: #16a34a; font-weight: 600; font-size: 0.95rem; }
.needs-review-banner { padding: 16px; background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; text-align: center; color: #d97706; font-weight: 600; font-size: 0.95rem; margin-bottom: 8px; }
.reviewing-hint { padding: 14px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; text-align: center; color: #2563eb; font-size: 0.88rem; margin-top: 12px; }
.clause-fp { font-size: 0.75rem; color: #7c3aed; font-style: italic; margin-top: 4px; }
.debate-block { margin-bottom: 10px; padding: 10px; background: #faf5ff; border-radius: 8px; border: 1px solid #ede9fe; }
.debate-clause-header { font-size: 0.82rem; font-weight: 700; color: #7c3aed; margin-bottom: 6px; }
.debate-round { margin: 3px 0; display: flex; align-items: flex-start; gap: 6px; flex-wrap: wrap; }
.round-label { font-size: 0.65rem; padding: 1px 6px; border-radius: 3px; font-weight: 700; }
.round-label.plaintiff { background: #fef2f2; color: #dc2626; }
.round-label.defendant { background: #f0fdf4; color: #16a34a; }
.debate-point { font-size: 0.78rem; color: #475569; }
.debate-verdict { margin-top: 6px; display: flex; align-items: center; gap: 8px; background: #fff; padding: 6px 10px; border-radius: 4px; }
.verdict-badge { font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 700; }
.verdict-badge.high { background: #fef2f2; color: #dc2626; }
.verdict-badge.medium { background: #fffbeb; color: #d97706; }
.verdict-badge.low { background: #f0fdf4; color: #16a34a; }
</style>
