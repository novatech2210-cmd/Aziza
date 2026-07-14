<script setup>
import { computed } from 'vue'

const props = defineProps({
  metrics: { type: Object, default: () => ({}) },
})

const ttft = computed(() => props.metrics.ttft || {})
const tokensPerSec = computed(() => props.metrics.tokens_per_sec || {})

function formatMs(val) {
  if (val == null) return '--'
  if (val < 1000) return `${Math.round(val)}ms`
  return `${(val / 1000).toFixed(1)}s`
}

function formatTps(val) {
  if (val == null) return '--'
  return `${Math.round(val)}`
}
</script>

<template>
  <div class="metrics-grid">
    <div class="metric-block">
      <div class="metric-label">TTFT P50</div>
      <div class="metric-val" :class="ttft.p50 < 500 ? 'green' : ttft.p50 < 2000 ? 'yellow' : 'red'">
        {{ formatMs(ttft.p50) }}
      </div>
    </div>
    <div class="metric-block">
      <div class="metric-label">TTFT P95</div>
      <div class="metric-val" :class="ttft.p95 < 1000 ? 'green' : ttft.p95 < 2000 ? 'yellow' : 'red'">
        {{ formatMs(ttft.p95) }}
      </div>
    </div>
    <div class="metric-block">
      <div class="metric-label">TTFT Avg</div>
      <div class="metric-val">{{ formatMs(ttft.avg) }}</div>
    </div>
    <div class="metric-divider"></div>
    <div class="metric-block">
      <div class="metric-label">Tokens/sec</div>
      <div class="metric-val accent">{{ formatTps(tokensPerSec.avg) }}</div>
    </div>
    <div class="metric-block">
      <div class="metric-label">Total Requests</div>
      <div class="metric-val">{{ metrics.total_requests ?? 0 }}</div>
    </div>
    <div class="metric-block">
      <div class="metric-label">Error Rate</div>
      <div class="metric-val" :class="metrics.error_rate < 5 ? 'green' : metrics.error_rate < 20 ? 'yellow' : 'red'">
        {{ metrics.error_rate ?? 0 }}%
      </div>
    </div>
    <div class="metric-block">
      <div class="metric-label">Success Rate</div>
      <div class="metric-val green">{{ metrics.success_rate ?? 100 }}%</div>
    </div>
    <div class="metric-block">
      <div class="metric-label">Req/min</div>
      <div class="metric-val">{{ metrics.requests_last_minute ?? 0 }}</div>
    </div>
  </div>
</template>

<style scoped>
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.75rem;
}

.metric-block {
  text-align: center;
  padding: 0.6rem 0.4rem;
  border-radius: 8px;
  background: var(--bg-tertiary);
}

.metric-label {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
  margin-bottom: 0.3rem;
}

.metric-val {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.metric-val.green { color: #22c55e; }
.metric-val.yellow { color: #eab308; }
.metric-val.red { color: #ef4444; }
.metric-val.accent { color: var(--accent); }

.metric-divider {
  width: 1px;
  background: var(--border);
  margin: 0.2rem 0;
}
</style>
