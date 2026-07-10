<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, authFetch } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import GpuDashboard from '../components/admin/GpuDashboard.vue'
import LatencyChart from '../components/admin/LatencyChart.vue'
import SessionMonitor from '../components/admin/SessionMonitor.vue'
import RagViewer from '../components/admin/RagViewer.vue'
import ErrorLog from '../components/admin/ErrorLog.vue'

const auth = useAuthStore()
const router = useRouter()
const theme = useThemeStore()

const ADMIN_WS = import.meta.env.VITE_ADMIN_WS_URL || `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/admin-api`
const ADMIN_API = import.meta.env.VITE_ADMIN_API_URL || '/admin-api'

const activeSessions = ref(0)
const gpu0Util = ref(0)
const gpu1Util = ref(0)
const errorRate = ref(0)
const gpuHistory = ref([])
const latencyHistory = ref([])
const heatmapData = ref(null)
const sessions = ref([])
const errors = ref([])

let ws = null

function connectWs() {
  const token = localStorage.getItem('aziza_token')
  ws = new WebSocket(`${ADMIN_WS}/admin-stats`, ["token", token])

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    activeSessions.value = data.sessions?.active ?? 0

    if (data.gpu?.length > 0) {
      gpu0Util.value = data.gpu[0]?.utilization_pct ?? 0
      gpu1Util.value = data.gpu[1]?.utilization_pct ?? 0
    }

    gpuHistory.value.push({ ts: data.ts, gpu0: gpu0Util.value, gpu1: gpu1Util.value })
    if (gpuHistory.value.length > 60) gpuHistory.value.shift()

    if (data.latency) {
      latencyHistory.value.push({ ts: data.ts, p50: data.latency.p50 ?? 0, p95: data.latency.p95 ?? 0 })
      if (latencyHistory.value.length > 60) latencyHistory.value.shift()
    }

    errorRate.value = data.error_rate ?? 0
  }

  ws.onclose = (e) => {
    if (e.code === 1008 || e.code === 4401) {
      auth.logout()
      return
    }
    setTimeout(connectWs, 3000)
  }
}

async function fetchSessions() {
  try {
    const res = await authFetch(`${ADMIN_API}/admin/sessions`)
    if (res.ok) sessions.value = await res.json()
  } catch {}
}

async function fetchErrors() {
  try {
    const res = await authFetch(`${ADMIN_API}/admin/errors`)
    if (res.ok) errors.value = await res.json()
  } catch {}
}

async function fetchHeatmap() {
  try {
    const res = await authFetch(`${ADMIN_API}/admin/latency/heatmap`)
    if (res.ok) heatmapData.value = await res.json()
  } catch {}
}

async function terminateSession(sessionId) {
  await authFetch(`${ADMIN_API}/admin/sessions/${sessionId}`, { method: 'DELETE' })
  await fetchSessions()
}

// Disconnect All modal
const showDisconnectModal = ref(false)
const disconnecting = ref(false)

async function disconnectAll() {
  disconnecting.value = true
  try {
    const res = await authFetch(`${ADMIN_API}/admin/sessions`, { method: 'DELETE' })
    if (res.ok) {
      const data = await res.json()
      window.dispatchEvent(new CustomEvent('aziza-toast', {
        detail: { type: 'success', message: `Disconnected ${data.count} session(s)` },
      }))
      sessions.value = []
      activeSessions.value = 0
    }
  } catch {}
  disconnecting.value = false
  showDisconnectModal.value = false
}

function gpuColorClass(pct) {
  if (pct < 70) return 'green'
  if (pct < 85) return 'yellow'
  return 'red'
}

onMounted(() => {
  connectWs()
  fetchSessions()
  fetchErrors()
  fetchHeatmap()
  const interval = setInterval(() => { fetchSessions(); fetchErrors(); fetchHeatmap() }, 10000)
  onUnmounted(() => clearInterval(interval))
})

onUnmounted(() => { if (ws) ws.close() })
</script>

<template>
  <div class="admin-page">
    <!-- Header -->
    <header class="admin-header">
      <div class="header-left">
        <router-link to="/chat" class="back-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back to Chat
        </router-link>
        <div class="header-title">
          <svg width="24" height="24" viewBox="0 0 48 48" fill="none">
            <rect width="48" height="48" rx="10" fill="url(#ag)" />
            <path d="M14 32L24 16L34 32H14Z" fill="white" opacity="0.9" />
            <defs><linearGradient id="ag" x1="0" y1="0" x2="48" y2="48"><stop stop-color="#14b8a6"/><stop offset="1" stop-color="#0891b2"/></linearGradient></defs>
          </svg>
          <h1>Admin Panel</h1>
        </div>
      </div>
      <div class="header-actions">
        <button class="theme-toggle" @click="theme.toggle()" :title="theme.isDark ? 'Switch to light mode' : 'Switch to dark mode'">
          <svg v-if="theme.isDark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
        </button>
        <router-link to="/personas" class="manage-btn" style="display: flex; align-items: center; gap: 0.4rem; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border); font-size: 0.8rem; font-weight: 500; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; text-decoration: none; transition: all 0.15s;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 00-3-3.87" />
            <path d="M16 3.13a4 4 0 010 7.75" />
          </svg>
          Manage Characters
        </router-link>
        <button class="danger-btn" @click="showDisconnectModal = true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18.36 6.64A9 9 0 115.64 18.36 9 9 0 0118.36 6.64zM12 8v4m0 4h.01"/></svg>
          Disconnect All
        </button>
      </div>
    </header>

    <!-- Stat Cards -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon sessions-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>
        </div>
        <div class="stat-info">
          <span class="stat-label">Active Sessions</span>
          <span class="stat-value">{{ activeSessions }}</span>
        </div>
      </div>

      <div class="stat-card">
        <div :class="['stat-icon', 'gpu-icon', gpuColorClass(gpu0Util)]">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg>
        </div>
        <div class="stat-info">
          <span class="stat-label">GPU-0</span>
          <span :class="['stat-value', gpuColorClass(gpu0Util)]">{{ gpu0Util }}%</span>
        </div>
      </div>

      <div class="stat-card">
        <div :class="['stat-icon', 'gpu-icon', gpuColorClass(gpu1Util)]">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg>
        </div>
        <div class="stat-info">
          <span class="stat-label">GPU-1</span>
          <span :class="['stat-value', gpuColorClass(gpu1Util)]">{{ gpu1Util }}%</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon error-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4m0 4h.01"/></svg>
        </div>
        <div class="stat-info">
          <span class="stat-label">Error Rate</span>
          <span class="stat-value">{{ errorRate }}<small>/min</small></span>
        </div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="chart-grid">
      <div class="panel">
        <h3 class="panel-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          GPU Utilization (60s)
        </h3>
        <div class="chart-wrapper">
          <GpuDashboard :gpu-history="gpuHistory" />
        </div>
      </div>
      <div class="panel">
        <h3 class="panel-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          Latency Heatmap (30 min)
        </h3>
        <div class="chart-wrapper heatmap-wrapper">
          <LatencyChart :latency-history="latencyHistory" :heatmap-data="heatmapData" />
        </div>
      </div>
    </div>

    <!-- Sessions + RAG Row -->
    <div class="chart-grid">
      <div class="panel">
        <h3 class="panel-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
          Active Sessions
        </h3>
        <SessionMonitor :sessions="sessions" @terminate="terminateSession" />
      </div>
      <div class="panel">
        <h3 class="panel-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>
          RAG Knowledge Base
        </h3>
        <RagViewer />
      </div>
    </div>

    <!-- Error Log -->
    <div class="panel">
      <h3 class="panel-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><path d="M12 9v4m0 4h.01"/></svg>
        Error Log
      </h3>
      <ErrorLog :errors="errors" />
    </div>

    <!-- Disconnect All Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showDisconnectModal" class="modal-overlay" @click.self="showDisconnectModal = false">
          <div class="modal-box">
            <div class="modal-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2" stroke-linecap="round">
                <path d="M18.36 6.64A9 9 0 115.64 18.36 9 9 0 0118.36 6.64zM12 8v4m0 4h.01"/>
              </svg>
            </div>
            <h3 class="modal-title">Disconnect All Sessions</h3>
            <p class="modal-message">
              This will forcefully disconnect <strong>{{ activeSessions }}</strong> active session(s).
              All connected users will be immediately disconnected from the chat.
            </p>
            <div class="modal-actions">
              <button class="modal-btn modal-cancel" @click="showDisconnectModal = false">Cancel</button>
              <button class="modal-btn modal-danger" @click="disconnectAll" :disabled="disconnecting">
                {{ disconnecting ? 'Disconnecting...' : 'Disconnect All' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: var(--bg-page);
  padding: 1.5rem;
}

/* Header */
.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--text-tertiary);
  text-decoration: none;
  font-size: 0.8rem;
  padding: 0.4rem 0.75rem;
  border-radius: 8px;
  transition: all 0.15s;
}

.back-btn:hover {
  color: var(--text-primary);
  background: var(--hover-overlay);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-title h1 {
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, #14b8a6, #06b6d4);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all 0.15s;
}

.theme-toggle:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.danger-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--danger-bg);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: var(--danger);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.danger-btn:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
}

/* Stat Cards */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.25rem;
  transition: border-color 0.2s;
}

.stat-card:hover {
  border-color: var(--card-hover-border);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sessions-icon {
  background: rgba(20, 184, 166, 0.1);
  color: #14b8a6;
}

.gpu-icon {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.gpu-icon.yellow {
  background: rgba(234, 179, 8, 0.1);
  color: #eab308;
}

.gpu-icon.red {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.error-icon {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.stat-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-tertiary);
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.stat-value.green { color: #22c55e; }
.stat-value.yellow { color: #eab308; }
.stat-value.red { color: #ef4444; }

.stat-value small {
  font-size: 0.75rem;
  color: var(--text-tertiary);
  font-weight: 500;
}

/* Chart Grid */
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 1.25rem;
}

/* Panels */
.panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}

.chart-grid .panel {
  margin-bottom: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.panel-title svg {
  color: var(--accent);
  opacity: 0.7;
}

.chart-wrapper {
  height: 220px;
}

.heatmap-wrapper {
  height: 280px;
}

/* Responsive */
@media (max-width: 1024px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .admin-page {
    padding: 1rem;
  }
  .stat-grid {
    grid-template-columns: 1fr;
  }
  .admin-header {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }
}

/* Disconnect All Modal */
.modal-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.modal-box {
  background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: 16px; padding: 1.75rem; width: 420px; max-width: 90vw;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  display: flex; flex-direction: column; align-items: center; text-align: center;
}
.modal-icon {
  width: 52px; height: 52px; border-radius: 50%;
  background: rgba(239, 68, 68, 0.1); display: flex; align-items: center;
  justify-content: center; margin-bottom: 1rem;
}
.modal-title {
  font-size: 1.05rem; font-weight: 700; color: var(--text-primary);
  margin: 0 0 0.5rem;
}
.modal-message {
  font-size: 0.84rem; color: var(--text-secondary); line-height: 1.55;
  margin: 0 0 1.5rem;
}
.modal-message strong { color: var(--text-primary); }
.modal-actions { display: flex; gap: 0.75rem; width: 100%; }
.modal-btn {
  flex: 1; padding: 0.6rem 1rem; border-radius: 10px; font-size: 0.84rem;
  font-weight: 600; cursor: pointer; transition: all 0.15s; border: none;
}
.modal-cancel {
  background: var(--bg-tertiary); color: var(--text-primary);
  border: 1px solid var(--border);
}
.modal-cancel:hover { background: var(--bg-secondary); }
.modal-danger {
  background: #ef4444; color: white;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
}
.modal-danger:hover { background: #dc2626; box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4); }
.modal-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-enter-active { transition: opacity 0.2s ease; }
.modal-leave-active { transition: opacity 0.15s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { animation: modal-pop 0.2s ease; }
@keyframes modal-pop {
  0% { transform: scale(0.9); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
</style>
