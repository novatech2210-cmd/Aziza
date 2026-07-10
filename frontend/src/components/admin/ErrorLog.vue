<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  errors: { type: Array, default: () => [] },
})

const filterLevel = ref('ALL')
const levels = ['ALL', 'ERROR', 'WARNING', 'INFO']

const filtered = computed(() => {
  if (filterLevel.value === 'ALL') return props.errors
  return props.errors.filter((e) => e.level?.toUpperCase() === filterLevel.value)
})
</script>

<template>
  <div>
    <div class="filter-row">
      <button
        v-for="level in levels"
        :key="level"
        @click="filterLevel = level"
        :class="['filter-btn', { active: filterLevel === level }]"
      >
        {{ level }}
      </button>
    </div>

    <div class="log-list">
      <div v-for="(err, i) in filtered" :key="i" class="log-entry">
        <span :class="['badge', (err.level || 'log').toLowerCase()]">
          {{ err.level || 'LOG' }}
        </span>
        <span class="log-time">
          {{ (err.ts || err.timestamp) ? new Date(err.ts || err.timestamp).toLocaleTimeString() : '' }}
        </span>
        <span v-if="err.service" class="log-service">[{{ err.service }}]</span>
        <span class="log-msg">{{ err.message }}</span>
      </div>
      <p v-if="!filtered.length" class="empty">No log entries</p>
    </div>
  </div>
</template>

<style scoped>
.filter-row { display: flex; gap: 0.35rem; margin-bottom: 0.75rem; }
.filter-btn {
  padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.7rem; font-weight: 600;
  border: 1px solid var(--border); background: transparent; color: var(--text-tertiary); cursor: pointer; transition: all 0.15s;
}
.filter-btn:hover { border-color: var(--border-light); color: var(--text-secondary); }
.filter-btn.active { background: linear-gradient(135deg, #14b8a6, #0891b2); border-color: transparent; color: white; }

.log-list { max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }

.log-entry {
  display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.8rem;
  padding: 0.5rem 0; border-bottom: 1px solid var(--border-light);
}

.badge {
  font-size: 0.6rem; font-weight: 700; padding: 0.15rem 0.45rem; border-radius: 4px;
  flex-shrink: 0; text-transform: uppercase; letter-spacing: 0.05em;
}
.badge.error { background: rgba(239,68,68,0.1); color: #f87171; }
.badge.warning { background: rgba(234,179,8,0.1); color: #eab308; }
.badge.info { background: rgba(59,130,246,0.1); color: #60a5fa; }
.badge.log { background: var(--hover-overlay); color: var(--text-tertiary); }

.log-time { font-size: 0.7rem; color: var(--text-muted); flex-shrink: 0; }
.log-service { font-size: 0.7rem; color: rgba(20,184,166,0.5); flex-shrink: 0; }
.log-msg { color: var(--text-secondary); word-break: break-all; }
.empty { text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem; }
</style>
