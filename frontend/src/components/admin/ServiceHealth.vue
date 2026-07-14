<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { authFetch } from '../../stores/auth'

const ADMIN_API = import.meta.env.VITE_ADMIN_API_URL || '/admin-api'

const services = ref([])
const loading = ref(true)
const lastCheck = ref(null)

const serviceOrder = ['api-gateway', 'orchestrator', 'personaplex', 'vllm-english', 'vllm-uzbek', 'redis', 'mongodb']

const serviceLabels = {
  'api-gateway': 'API Gateway',
  'orchestrator': 'Orchestrator',
  'personaplex': 'PersonaPlex',
  'vllm-english': 'vLLM English',
  'vllm-uzbek': 'vLLM Uzbek',
  'redis': 'Redis',
  'mongodb': 'MongoDB',
}

const servicePorts = {
  'api-gateway': 8080,
  'orchestrator': 8001,
  'personaplex': 8000,
  'vllm-english': 8002,
  'vllm-uzbek': 8003,
}

async function checkServices() {
  loading.value = true
  const results = []

  for (const name of serviceOrder) {
    const port = servicePorts[name]
    let status = 'unknown'
    let latency = null

    if (port) {
      try {
        const start = Date.now()
        const res = await fetch(`/api/health-check?port=${port}`, { signal: AbortSignal.timeout(3000) })
        latency = Date.now() - start
        status = res.ok ? 'healthy' : 'degraded'
      } catch {
        status = 'down'
      }
    } else {
      status = 'external'
    }

    results.push({ name, label: serviceLabels[name] || name, status, latency, port })
  }

  services.value = results
  lastCheck.value = new Date()
  loading.value = false
}

let interval
onMounted(() => {
  checkServices()
  interval = setInterval(checkServices, 15000)
})
onUnmounted(() => clearInterval(interval))

function statusColor(status) {
  if (status === 'healthy') return 'green'
  if (status === 'degraded') return 'yellow'
  if (status === 'down') return 'red'
  return 'gray'
}

function statusIcon(status) {
  if (status === 'healthy') return 'M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3'
  if (status === 'degraded') return 'M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4m0 4h.01'
  if (status === 'down') return 'M18.36 6.64A9 9 0 115.64 18.36 9 9 0 0118.36 6.64zM12 8v4m0 4h.01'
  return 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zm0-14v4m0 4h.01'
}
</script>

<template>
  <div class="health-grid">
    <div
      v-for="svc in services"
      :key="svc.name"
      :class="['health-item', statusColor(svc.status)]"
    >
      <div class="health-left">
        <div :class="['health-dot', statusColor(svc.status)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path :d="statusIcon(svc.status)" />
          </svg>
        </div>
        <div class="health-info">
          <span class="health-name">{{ svc.label }}</span>
          <span class="health-port" v-if="svc.port">:{{ svc.port }}</span>
        </div>
      </div>
      <div class="health-right">
        <span :class="['health-status', statusColor(svc.status)]">{{ svc.status }}</span>
        <span class="health-latency" v-if="svc.latency">{{ svc.latency }}ms</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.5rem;
}

.health-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  transition: border-color 0.2s;
}

.health-item:hover {
  border-color: var(--card-hover-border);
}

.health-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.health-dot {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.health-dot.green { background: rgba(34, 197, 94, 0.12); color: #22c55e; }
.health-dot.yellow { background: rgba(234, 179, 8, 0.12); color: #eab308; }
.health-dot.red { background: rgba(239, 68, 68, 0.12); color: #ef4444; }
.health-dot.gray { background: rgba(107, 114, 128, 0.12); color: #6b7280; }

.health-info {
  display: flex;
  align-items: baseline;
  gap: 0.15rem;
}

.health-name {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.health-port {
  font-size: 0.72rem;
  color: var(--text-tertiary);
  font-family: monospace;
}

.health-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.health-status {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.health-status.green { color: #22c55e; }
.health-status.yellow { color: #eab308; }
.health-status.red { color: #ef4444; }
.health-status.gray { color: #6b7280; }

.health-latency {
  font-size: 0.7rem;
  color: var(--text-tertiary);
  font-family: monospace;
}
</style>
