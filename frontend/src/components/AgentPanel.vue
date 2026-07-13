<template>
  <div class="agent-panel-wrap">
    <h2>🤖 Agent 状态</h2>
    <div v-if="agents.length === 0" class="empty-state">
      等待审批任务...
    </div>
    <div v-for="agent in agents" :key="agent.id" class="agent-card">
      <div class="agent-header">
        <span :class="['agent-dot', statusClass(agent.status)]"></span>
        <span class="agent-name">{{ formatId(agent.id) }}</span>
      </div>
      <span :class="['agent-badge', statusClass(agent.status)]">
        {{ agent.status }}
      </span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AgentPanel',
  props: {
    agents: { type: Array, default: () => [] },
  },
  methods: {
    statusClass(status) {
      const map = {
        thinking: 'active', acting: 'active',
        done: 'done', idle: 'idle',
        waiting: 'waiting', error: 'error',
      }
      return map[status] || 'idle'
    },
    formatId(id) {
      if (!id) return 'unknown'
      if (id.startsWith('master')) return '🧠 Master Agent'
      if (id.includes('extract')) return '📄 Extract Agent'
      if (id.includes('comply')) return '⚖️ Comply Agent'
      if (id.includes('risk')) return '⚠️ Risk Agent'
      return id.length > 18 ? id.slice(0, 16) + '...' : id
    },
  },
}
</script>

<style scoped>
.agent-panel-wrap { padding: 4px 0; }
.agent-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #1e293b;
}
.agent-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.agent-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  animation: pulse 2s infinite;
}
.agent-dot.active { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
.agent-dot.idle { background: #64748b; }
.agent-dot.waiting { background: #f59e0b; box-shadow: 0 0 8px #f59e0b; }
.agent-dot.done { background: #3b82f6; }
.agent-dot.error { background: #ef4444; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.agent-name {
  font-size: 0.85rem;
  color: #e2e8f0;
}
.agent-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}
.agent-badge.active { background: #065f46; color: #6ee7b7; }
.agent-badge.idle { background: #1e293b; color: #64748b; }
.agent-badge.waiting { background: #78350f; color: #fcd34d; }
.agent-badge.done { background: #1e3a5f; color: #93c5fd; }
.agent-badge.error { background: #7f1d1d; color: #fca5a5; }
.empty-state { text-align: center; color: #475569; padding: 40px 0; font-size: 0.85rem; }
</style>
