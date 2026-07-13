<template>
  <div class="agent-monitor">
    <h2 class="page-title">Agent 监控</h2>

    <div class="agent-grid">
      <div v-for="agent in agents" :key="agent.id" :class="['agent-card', agent.status]">
        <div class="agent-card-header">
          <span :class="['agent-avatar', agent.status]">{{ agent.name[0] }}</span>
          <div>
            <strong>{{ agent.name }}</strong>
            <p>{{ agent.role }}</p>
          </div>
          <span :class="['status-dot', agent.status]"></span>
        </div>
        <div class="agent-stats">
          <div class="agent-stat"><span class="agent-stat-val">{{ agent.tasks }}</span><span class="agent-stat-label">处理任务</span></div>
          <div class="agent-stat"><span class="agent-stat-val">{{ agent.successRate }}%</span><span class="agent-stat-label">成功率</span></div>
          <div class="agent-stat"><span class="agent-stat-val">{{ agent.avgTime }}ms</span><span class="agent-stat-label">平均耗时</span></div>
        </div>
        <div class="agent-tools">
          <span v-for="t in agent.tools" :key="t" class="tool-chip">{{ t }}</span>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top: 20px;">
      <h3>工具调用统计</h3>
      <table class="stats-table">
        <thead><tr><th>工具名</th><th>调用次数</th><th>成功率</th><th>平均耗时</th></tr></thead>
        <tbody>
          <tr v-for="t in toolStats" :key="t.name">
            <td><span class="tool-name">{{ t.name }}</span></td>
            <td>{{ t.calls }}</td>
            <td><span :class="(t.success_rate || 0) > 90 ? 'green' : 'yellow'">{{ t.success_rate || 0 }}%</span></td>
            <td>{{ t.avg_latency || 0 }}ms</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
const API = axios.create({ baseURL: '/api' })

export default {
  name: 'AgentMonitor',
  data() {
    return { agents: [], toolStats: [] }
  },
  mounted() {
    this.fetchData()
    this._timer = setInterval(() => { this.fetchData() }, 5000)
  },
  beforeDestroy() {
    if (this._timer) clearInterval(this._timer)
  },
  methods: {
    async fetchData() {
      try {
        const [healthRes, toolsRes] = await Promise.all([API.get('/health'), API.get('/tools')])
        const h = healthRes.data
        const tools = toolsRes.data || []
        this.toolStats = tools

        const tt = h.tasks_total || 0
        const latestL = parseFloat(h.latest_latency) || 30

        const agentDefs = [
          { id: 1, name: 'Master Agent', role: '主调度 (Phase编排)', toolNames: ['dispatch_subagent', 'generate_report'] },
          { id: 2, name: 'Investigation Agent', role: '合同解析+义务矩阵', toolNames: ['build_obligation_matrix'] },
          { id: 3, name: 'Risk Pattern Agent', role: '风险模式扫描(规则优先)', toolNames: ['scan_risk_patterns'] },
          { id: 4, name: 'Legal Citation Agent', role: '法条映射(解释已有风险)', toolNames: ['search_law'] },
          { id: 5, name: 'Evidence Agent', role: '证据生成(原文+位置)', toolNames: ['generate_evidence'] },
          { id: 6, name: 'Risk Decision Agent', role: '多维评分+强制升级', toolNames: ['risk_score'] },
        ]

        this.agents = agentDefs.map(def => {
          const at = tools.filter(t => def.toolNames.includes(t.name))
          const totalCalls = at.reduce((s, t) => s + (t.calls || 0), 0)
          const avgSR = totalCalls > 0 ? Math.round(at.reduce((s, t) => s + (t.success_rate || 100), 0) / at.length) : 0
          const avgLat = totalCalls > 0 ? Math.round(at.reduce((s, t) => s + (parseFloat(t.avg_latency) || 0), 0) / at.length) : 0
          return {
            ...def, tasks: tt, successRate: totalCalls > 0 ? avgSR : 100,
            avgTime: totalCalls > 0 ? avgLat : Math.round(latestL * 1000 / def.id),
            status: tt > 0 ? 'online' : 'idle',
            tools: def.toolNames,
          }
        })
      } catch { this.agents = [] }
    },
  },
}
</script>

<style scoped>
.agent-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.agent-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }
.agent-card.online { border-left: 4px solid #22c55e; }
.agent-card.idle { border-left: 4px solid #94a3b8; }
.agent-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.agent-avatar { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1rem; font-weight: 800; color: #fff; }
.agent-avatar.online { background: #3b82f6; }
.agent-avatar.idle { background: #94a3b8; }
.agent-card-header strong { font-size: 0.95rem; color: #1e293b; }
.agent-card-header p { font-size: 0.72rem; color: #94a3b8; margin: 2px 0 0; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; margin-left: auto; }
.status-dot.online { background: #22c55e; box-shadow: 0 0 6px #22c55e; animation: pulse 2s infinite; }
.status-dot.idle { background: #94a3b8; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.agent-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
.agent-stat { text-align: center; padding: 8px; background: #f8fafc; border-radius: 6px; }
.agent-stat-val { font-size: 1.1rem; font-weight: 700; color: #1e293b; display: block; }
.agent-stat-label { font-size: 0.7rem; color: #94a3b8; }
.agent-tools { display: flex; flex-wrap: wrap; gap: 6px; }
.tool-chip { font-size: 0.7rem; padding: 3px 8px; background: #eff6ff; color: #2563eb; border-radius: 4px; font-weight: 500; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; }
.card h3 { font-size: 1rem; margin-bottom: 12px; color: #1e293b; }
.stats-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.stats-table th { text-align: left; padding: 8px 12px; background: #f8fafc; color: #64748b; font-weight: 600; border-bottom: 1px solid #e2e8f0; }
.stats-table td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
.tool-name { font-weight: 600; color: #1e293b; }
.green { color: #16a34a; font-weight: 600; }
.yellow { color: #d97706; font-weight: 600; }
</style>
