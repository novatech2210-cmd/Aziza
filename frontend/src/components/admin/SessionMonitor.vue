<script setup>
defineProps({
  sessions: { type: Array, default: () => [] },
})

const emit = defineEmits(['terminate'])

function formatDuration(createdAt) {
  if (!createdAt) return '--'
  const diff = Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000)
  const mins = Math.floor(diff / 60)
  const secs = diff % 60
  return `${mins}m ${secs}s`
}
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>User ID</th>
          <th>Language</th>
          <th>Duration</th>
          <th>Messages</th>
          <th>Last Active</th>
          <th style="text-align:right">Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in sessions" :key="s.session_id || s.id">
          <td class="mono">{{ s.user_id || '--' }}</td>
          <td><span class="lang-badge">{{ (s.language || 'en').toUpperCase() }}</span></td>
          <td>{{ formatDuration(s.created_at) }}</td>
          <td>{{ s.message_count ?? 0 }}</td>
          <td class="dim">{{ s.last_active ? new Date(s.last_active).toLocaleTimeString() : '--' }}</td>
          <td style="text-align:right">
            <button @click="emit('terminate', s.session_id || s.id)" class="term-btn">Terminate</button>
          </td>
        </tr>
        <tr v-if="!sessions.length">
          <td colspan="6" class="empty">No active sessions</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap { overflow-x: auto; max-height: 300px; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
th { text-align: left; padding: 0.6rem 0.75rem; font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); border-bottom: 1px solid var(--border); }
td { padding: 0.65rem 0.75rem; color: var(--text-secondary); border-bottom: 1px solid var(--border-light); }
tbody tr:hover { background: var(--hover-overlay); }
.mono { font-family: 'SF Mono', Monaco, Consolas, monospace; font-size: 0.75rem; color: var(--text-secondary); }
.dim { font-size: 0.75rem; color: var(--text-tertiary); }
.lang-badge { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.05em; background: rgba(20,184,166,0.1); color: #14b8a6; padding: 0.15rem 0.5rem; border-radius: 4px; }
.term-btn { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.15); color: #f87171; font-size: 0.72rem; font-weight: 500; padding: 0.3rem 0.75rem; border-radius: 6px; cursor: pointer; transition: all 0.15s; }
.term-btn:hover { background: rgba(239,68,68,0.15); border-color: rgba(239,68,68,0.3); }
.empty { text-align: center; padding: 2rem; color: var(--text-muted); }
</style>
