<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { authFetch } from '../../stores/auth'

const ADMIN_API = import.meta.env.VITE_ADMIN_API_URL || '/admin-api'

const props = defineProps({
  logs: { type: Array, default: () => [] },
  stats: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['refresh'])

const filterService = ref('ALL')
const filterLevel = ref('ALL')
const searchQuery = ref('')
const autoRefresh = ref(true)
const loading = ref(false)

const services = ['ALL', 'api-gateway', 'orchestrator', 'moshi-worker', 'personaplex', 'vllm-english', 'vllm-uzbek', 'livekit-bot']
const levels = ['ALL', 'error', 'warn', 'info', 'debug']

const filteredLogs = computed(() => {
  let result = props.logs
  if (filterService.value !== 'ALL') {
    result = result.filter(l => l.service === filterService.value)
  }
  if (filterLevel.value !== 'ALL') {
    result = result.filter(l => l.level === filterLevel.value)
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(l => l.message?.toLowerCase().includes(q) || l.service?.toLowerCase().includes(q))
  }
  return result
})

const levelCounts = computed(() => {
  const counts = { error: 0, warn: 0, info: 0, debug: 0 }
  for (const log of props.logs) {
    if (counts[log.level] !== undefined) counts[log.level]++
  }
  return counts
})

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatFullTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString()
}

let refreshInterval = null

onMounted(() => {
  if (autoRefresh.value) {
    refreshInterval = setInterval(() => emit('refresh'), 15000)
  }
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="log-viewer">
    <!-- Controls -->
    <div class="log-controls">
      <div class="control-group">
        <label>Service</label>
        <select v-model="filterService" class="log-select">
          <option v-for="s in services" :key="s" :value="s">{{ s === 'ALL' ? 'All Services' : s }}</option>
        </select>
      </div>
      <div class="control-group">
        <label>Level</label>
        <div class="level-filters">
          <button
            v-for="level in levels"
            :key="level"
            @click="filterLevel = level"
            :class="['level-btn', level, { active: filterLevel === level }]"
          >
            {{ level === 'ALL' ? 'ALL' : level.toUpperCase() }}
            <span v-if="level !== 'ALL' && levelCounts[level]" class="count">{{ levelCounts[level] }}</span>
          </button>
        </div>
      </div>
      <div class="control-group search-group">
        <label>Search</label>
        <input v-model="searchQuery" placeholder="Filter logs..." class="log-input" />
      </div>
      <div class="control-group">
        <label class="auto-refresh-label">
          <input type="checkbox" v-model="autoRefresh" @change="autoRefresh ? (refreshInterval = setInterval(() => emit('refresh'), 15000)) : clearInterval(refreshInterval)" />
          Auto-refresh
        </label>
      </div>
    </div>

    <!-- Stats Summary -->
    <div v-if="stats.hourly_by_service?.length" class="log-stats">
      <div v-for="s in stats.hourly_by_service" :key="s.service" class="stat-chip">
        <span class="chip-service">{{ s.service }}</span>
        <span class="chip-count">{{ s.count }}/hr</span>
      </div>
      <div class="stat-chip total">
        <span class="chip-count">{{ stats.total_today || 0 }} today</span>
      </div>
    </div>

    <!-- Log Entries -->
    <div class="log-entries">
      <div v-for="(log, i) in filteredLogs" :key="log._id || i" :class="['log-entry', log.level]">
        <span :class="['level-badge', log.level]">{{ log.level }}</span>
        <span class="log-time" :title="formatFullTime(log.createdAt)">{{ formatTime(log.createdAt) }}</span>
        <span class="log-service">[{{ log.service }}]</span>
        <span class="log-message">{{ log.message }}</span>
        <span v-if="log.correlationId" class="log-correlation" :title="log.correlationId">corr:{{ log.correlationId.slice(0, 8) }}</span>
      </div>
      <p v-if="!filteredLogs.length" class="empty-state">No log entries match filters</p>
    </div>
  </div>
</template>

<style scoped>
.log-viewer {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.log-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: flex-end;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.control-group label {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.log-select, .log-input {
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 0.75rem;
  outline: none;
  transition: border-color 0.15s;
}

.log-select:focus, .log-input:focus {
  border-color: var(--accent);
}

.log-input {
  min-width: 180px;
}

.search-group {
  flex: 1;
  min-width: 180px;
}

.level-filters {
  display: flex;
  gap: 0.25rem;
}

.level-btn {
  padding: 0.35rem 0.6rem;
  border-radius: 6px;
  font-size: 0.65rem;
  font-weight: 700;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.level-btn:hover { border-color: var(--border-light); color: var(--text-secondary); }
.level-btn.active { border-color: transparent; color: white; }
.level-btn.active.error { background: #ef4444; }
.level-btn.active.warn { background: #eab308; }
.level-btn.active.info { background: #3b82f6; }
.level-btn.active.debug { background: #6b7280; }
.level-btn.active.ALL { background: linear-gradient(135deg, #14b8a6, #0891b2); }

.count {
  font-size: 0.6rem;
  opacity: 0.8;
}

.auto-refresh-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.auto-refresh-label input {
  accent-color: var(--accent);
}

.log-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.stat-chip {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-light);
  font-size: 0.65rem;
}

.chip-service { color: var(--text-tertiary); font-weight: 500; }
.chip-count { color: var(--accent); font-weight: 700; }
.stat-chip.total { border-color: var(--accent); }

.log-entries {
  max-height: 400px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.72rem;
  padding: 0.4rem 0.5rem;
  border-bottom: 1px solid var(--border-light);
  transition: background 0.1s;
}

.log-entry:hover { background: var(--hover-overlay); }
.log-entry.error { background: rgba(239, 68, 68, 0.03); }
.log-entry.warn { background: rgba(234, 179, 8, 0.03); }

.level-badge {
  font-size: 0.55rem;
  font-weight: 800;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex-shrink: 0;
  min-width: 36px;
  text-align: center;
}

.level-badge.error { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.level-badge.warn { background: rgba(234, 179, 8, 0.15); color: #eab308; }
.level-badge.info { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.level-badge.debug { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }

.log-time {
  font-size: 0.65rem;
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 65px;
}

.log-service {
  font-size: 0.65rem;
  color: rgba(20, 184, 166, 0.6);
  flex-shrink: 0;
}

.log-message {
  color: var(--text-secondary);
  word-break: break-all;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-correlation {
  font-size: 0.55rem;
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0.6;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}
</style>
