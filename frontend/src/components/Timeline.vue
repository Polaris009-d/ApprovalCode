<template>
  <div class="timeline-wrap">
    <div
      v-for="(step, index) in steps"
      :key="index"
      :class="['timeline-item', step.type]"
    >
      <div class="timeline-marker">
        <span class="step-icon">{{ iconFor(step) }}</span>
        <div v-if="index < steps.length - 1" class="timeline-line"></div>
      </div>
      <div class="timeline-body">
        <div class="step-header">
          <span class="step-num">#{{ step.step || index + 1 }}</span>
          <span class="step-agent">{{ step.agent || 'system' }}</span>
          <span class="step-duration">{{ (step.duration_ms || 0).toFixed(0) }}ms</span>
        </div>
        <div class="step-content">{{ step.content }}</div>
        <div v-if="step.tool" class="step-tool">
          🔧 {{ step.tool }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Timeline',
  props: {
    steps: { type: Array, default: () => [] },
  },
  methods: {
    iconFor(step) {
      const map = {
        think: '🧠', plan: '📋', act: '🔧', observe: '👁️',
        error: '❌', done: '✅',
      }
      return map[step.type] || '•'
    },
  },
}
</script>

<style scoped>
.timeline-wrap { padding: 4px 0; }
.timeline-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } }

.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 32px;
}
.step-icon { font-size: 1.1rem; }
.timeline-line {
  width: 2px;
  flex: 1;
  background: #334155;
  margin-top: 4px;
}

.timeline-body { flex: 1; }
.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.step-num {
  color: #64748b;
  font-size: 0.75rem;
  font-family: monospace;
}
.step-agent {
  color: #3b82f6;
  font-size: 0.75rem;
  background: #1e3a5f;
  padding: 1px 6px;
  border-radius: 3px;
}
.step-duration {
  margin-left: auto;
  color: #64748b;
  font-size: 0.7rem;
  font-family: monospace;
}
.step-content {
  font-size: 0.85rem;
  color: #cbd5e1;
  line-height: 1.4;
}
.step-tool {
  margin-top: 4px;
  font-size: 0.75rem;
  color: #fbbf24;
  background: #422006;
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
}

.timeline-item.think .step-icon { color: #a78bfa; }
.timeline-item.plan .step-icon { color: #60a5fa; }
.timeline-item.act .step-icon { color: #fbbf24; }
.timeline-item.observe .step-icon { color: #34d399; }
.timeline-item.error .step-icon { color: #f87171; }
</style>
