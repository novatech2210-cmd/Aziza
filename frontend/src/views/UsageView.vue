<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, authFetch } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

const auth = useAuthStore()
const theme = useThemeStore()
const router = useRouter()

const AUTH_API = import.meta.env.VITE_AUTH_API_URL || '/api'

const usage = ref(null)
const tierInfo = ref(null)
const tiers = ref({})
const loading = ref(true)

async function fetchAll() {
  loading.value = true
  try {
    const [usageRes, tierRes, tiersRes] = await Promise.all([
      authFetch(`${AUTH_API}/me/usage`),
      authFetch(`${AUTH_API}/me/tier`),
      authFetch(`${AUTH_API}/tiers`),
    ])
    if (usageRes.ok) usage.value = await usageRes.json()
    if (tierRes.ok) tierInfo.value = await tierRes.json()
    if (tiersRes.ok) tiers.value = await tiersRes.json()
  } catch (err) {
    console.error('[Usage] Failed to fetch:', err)
  }
  loading.value = false
}

async function selectTier(tierKey) {
  if (tierKey === tierInfo.value?.tier) return
  try {
    const res = await authFetch(`${AUTH_API}/me/tier`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tier: tierKey }),
    })
    if (res.ok) {
      tierInfo.value = await res.json()
      await fetchAll()
      window.dispatchEvent(new CustomEvent('aziza-toast', {
        detail: { type: 'success', message: `Plan changed to ${tierInfo.value.label}` },
      }))
    }
  } catch (err) {
    console.error('[Usage] Failed to change tier:', err)
  }
}

function usagePercent(used, limit) {
  if (limit <= 0) return 0 // unlimited
  return Math.min((used / limit) * 100, 100)
}

function formatLimit(val) {
  if (val === -1) return 'Unlimited'
  return val.toLocaleString()
}

const weekDays = computed(() => {
  if (!usage.value?.weekly) return []
  return usage.value.weekly.map(d => ({
    ...d,
    dayLabel: new Date(d.date).toLocaleDateString([], { weekday: 'short' }),
  }))
})

const maxWeeklyMessages = computed(() => {
  if (!weekDays.value.length) return 1
  return Math.max(...weekDays.value.map(d => d.messages), 1)
})

onMounted(fetchAll)
</script>

<template>
  <div class="usage-page">
    <header class="page-header">
      <div class="header-left">
        <router-link to="/chat" class="back-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back to Chat
        </router-link>
        <h1 class="page-title">Usage & Plan</h1>
      </div>
      <button class="theme-toggle" @click="theme.toggle()">
        <svg v-if="theme.isDark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
        <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
      </button>
    </header>

    <div v-if="loading" class="loading">Loading...</div>

    <template v-else>
      <!-- Current Plan -->
      <section class="section">
        <h2 class="section-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
          Current Plan
        </h2>
        <div class="plan-card">
          <div class="plan-badge" :class="tierInfo?.tier">{{ tierInfo?.label || 'Free' }}</div>
          <div class="plan-details">
            <div class="plan-stat">
              <span class="plan-stat-label">Daily messages</span>
              <span class="plan-stat-value">{{ formatLimit(tierInfo?.daily_messages ?? 50) }}</span>
            </div>
            <div class="plan-stat">
              <span class="plan-stat-label">Max sessions</span>
              <span class="plan-stat-value">{{ formatLimit(tierInfo?.max_sessions ?? 10) }}</span>
            </div>
          </div>
          <span class="upgrade-hint">Click a plan below to switch</span>
        </div>
      </section>

      <!-- Tier Comparison -->
      <section class="section">
        <h2 class="section-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
          Available Plans
        </h2>
        <div class="tiers-grid">
          <div
            v-for="(tier, key) in tiers"
            :key="key"
            :class="['tier-card', { current: tierInfo?.tier === key }]"
            @click="selectTier(key)"
          >
            <div class="tier-badge" :class="key">{{ tier.label }}</div>
            <div class="tier-limits">
              <p><strong>{{ formatLimit(tier.daily_messages) }}</strong> messages/day</p>
              <p><strong>{{ formatLimit(tier.max_sessions) }}</strong> sessions</p>
            </div>
            <div v-if="tierInfo?.tier === key" class="tier-current-label">Current</div>
          </div>
        </div>
      </section>

      <!-- Today's Usage -->
      <section class="section">
        <h2 class="section-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          Today's Usage
        </h2>
        <div class="usage-meters">
          <div class="meter-card">
            <div class="meter-header">
              <span class="meter-label">Messages</span>
              <span class="meter-value">{{ usage?.today?.messages_today ?? 0 }} / {{ formatLimit(tierInfo?.daily_messages ?? 50) }}</span>
            </div>
            <div class="meter-bar">
              <div
                class="meter-fill messages"
                :style="{ width: usagePercent(usage?.today?.messages_today ?? 0, tierInfo?.daily_messages ?? 50) + '%' }"
              />
            </div>
          </div>
          <div class="meter-card">
            <div class="meter-header">
              <span class="meter-label">Sessions</span>
              <span class="meter-value">{{ usage?.today?.sessions_today ?? 0 }} / {{ formatLimit(tierInfo?.max_sessions ?? 10) }}</span>
            </div>
            <div class="meter-bar">
              <div
                class="meter-fill sessions"
                :style="{ width: usagePercent(usage?.today?.sessions_today ?? 0, tierInfo?.max_sessions ?? 10) + '%' }"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Weekly Chart -->
      <section class="section">
        <h2 class="section-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
          Weekly Activity
        </h2>
        <div class="weekly-chart" v-if="weekDays.length">
          <div class="chart-row" v-for="day in weekDays" :key="day.date">
            <span class="chart-day">{{ day.dayLabel }}</span>
            <div class="chart-bar-wrap">
              <div class="chart-bar" :style="{ width: (day.messages / maxWeeklyMessages * 100) + '%' }">
                <span class="chart-bar-label" v-if="day.messages > 0">{{ day.messages }}</span>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="empty-text">No activity this week</p>
      </section>

      <!-- Totals -->
      <section class="section">
        <h2 class="section-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          All Time
        </h2>
        <div class="totals-grid">
          <div class="total-card">
            <span class="total-value">{{ (usage?.totals?.total_messages ?? 0).toLocaleString() }}</span>
            <span class="total-label">Messages</span>
          </div>
          <div class="total-card">
            <span class="total-value">{{ (usage?.totals?.total_sessions ?? 0).toLocaleString() }}</span>
            <span class="total-label">Sessions</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.usage-page {
  min-height: 100vh;
  background: var(--bg-page);
  padding: 1.5rem;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}

.header-left { display: flex; align-items: center; gap: 1.5rem; }

.back-btn {
  display: flex; align-items: center; gap: 0.4rem; color: var(--text-tertiary);
  text-decoration: none; font-size: 0.8rem; padding: 0.4rem 0.75rem; border-radius: 8px; transition: all 0.15s;
}
.back-btn:hover { color: var(--text-primary); background: var(--hover-overlay); }

.page-title {
  font-size: 1.25rem; font-weight: 700;
  background: linear-gradient(135deg, #14b8a6, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}

.theme-toggle {
  display: flex; align-items: center; justify-content: center; width: 36px; height: 36px;
  border-radius: 8px; background: var(--bg-secondary); border: 1px solid var(--border);
  color: var(--text-tertiary); cursor: pointer; transition: all 0.15s;
}
.theme-toggle:hover { color: var(--accent); border-color: var(--accent); }

.loading { text-align: center; padding: 4rem; color: var(--text-muted); }

/* Sections */
.section { margin-bottom: 2rem; }
.section-title {
  display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; font-weight: 600;
  color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem;
}
.section-title svg { color: var(--accent); opacity: 0.7; }

/* Plan Card */
.plan-card {
  display: flex; align-items: center; gap: 1.5rem;
  background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 14px; padding: 1.5rem;
}

.plan-badge {
  font-size: 1.1rem; font-weight: 800; letter-spacing: 0.05em; padding: 0.6rem 1.2rem;
  border-radius: 10px; text-transform: uppercase;
}
.plan-badge.free { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.plan-badge.basic { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.plan-badge.pro { background: rgba(168, 85, 247, 0.15); color: #a78bfa; }
.plan-badge.enterprise { background: rgba(234, 179, 8, 0.15); color: #facc15; }

.plan-details { flex: 1; display: flex; gap: 2rem; }
.plan-stat { display: flex; flex-direction: column; gap: 0.15rem; }
.plan-stat-label { font-size: 0.7rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.05em; }
.plan-stat-value { font-size: 1.2rem; font-weight: 700; color: var(--text-primary); }

.upgrade-hint {
  font-size: 0.72rem; color: var(--text-tertiary); font-style: italic;
}

/* Tiers Grid */
.tiers-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; }

.tier-card {
  background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px;
  padding: 1rem; text-align: center; transition: all 0.2s; position: relative; cursor: pointer;
}
.tier-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(20, 184, 166, 0.15); }
.tier-card.current { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); cursor: default; }

.tier-badge {
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; padding: 0.3rem 0.8rem;
  border-radius: 6px; display: inline-block; margin-bottom: 0.75rem; text-transform: uppercase;
}
.tier-badge.free { background: rgba(107, 114, 128, 0.12); color: #9ca3af; }
.tier-badge.basic { background: rgba(59, 130, 246, 0.12); color: #60a5fa; }
.tier-badge.pro { background: rgba(168, 85, 247, 0.12); color: #a78bfa; }
.tier-badge.enterprise { background: rgba(234, 179, 8, 0.12); color: #facc15; }

.tier-limits { font-size: 0.78rem; color: var(--text-secondary); line-height: 1.8; }
.tier-limits strong { color: var(--text-primary); }

.tier-current-label {
  position: absolute; top: -8px; right: 12px; font-size: 0.6rem; font-weight: 700;
  background: var(--accent); color: white; padding: 2px 8px; border-radius: 4px;
  text-transform: uppercase; letter-spacing: 0.05em;
}

/* Usage Meters */
.usage-meters { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }

.meter-card {
  background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; padding: 1rem;
}

.meter-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; }
.meter-label { font-size: 0.78rem; font-weight: 600; color: var(--text-secondary); }
.meter-value { font-size: 0.72rem; color: var(--text-tertiary); }

.meter-bar { height: 8px; background: var(--bg-tertiary); border-radius: 4px; overflow: hidden; }
.meter-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.meter-fill.messages { background: linear-gradient(90deg, #14b8a6, #06b6d4); }
.meter-fill.sessions { background: linear-gradient(90deg, #a78bfa, #8b5cf6); }

/* Weekly Chart */
.weekly-chart { display: flex; flex-direction: column; gap: 0.5rem; }
.chart-row { display: flex; align-items: center; gap: 0.75rem; }
.chart-day { width: 36px; font-size: 0.72rem; font-weight: 600; color: var(--text-tertiary); text-align: right; }
.chart-bar-wrap { flex: 1; height: 24px; background: var(--bg-tertiary); border-radius: 6px; overflow: hidden; }
.chart-bar {
  height: 100%; background: linear-gradient(90deg, #14b8a6, #06b6d4); border-radius: 6px;
  display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;
  min-width: 0; transition: width 0.5s ease;
}
.chart-bar-label { font-size: 0.65rem; font-weight: 700; color: white; }

/* Totals */
.totals-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.total-card {
  background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px;
  padding: 1.5rem; text-align: center; display: flex; flex-direction: column; gap: 0.25rem;
}
.total-value { font-size: 2rem; font-weight: 800; color: var(--text-primary); }
.total-label { font-size: 0.72rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }

.empty-text { text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem; }

@media (max-width: 768px) {
  .tiers-grid { grid-template-columns: repeat(2, 1fr); }
  .plan-card { flex-direction: column; align-items: flex-start; }
  .plan-details { flex-direction: column; gap: 0.5rem; }
}

@media (max-width: 480px) {
  .usage-page { padding: 1rem; }
  .tiers-grid { grid-template-columns: 1fr; }
  .usage-meters { grid-template-columns: 1fr; }
  .totals-grid { grid-template-columns: 1fr; }
}
</style>
