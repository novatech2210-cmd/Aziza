<script setup>
import { ref, onMounted, computed } from 'vue'
import { authFetch } from '../../stores/auth'

const ADMIN_API = import.meta.env.VITE_ADMIN_API_URL || '/admin-api'

const stats = ref({ doc_count: 0, source_count: 0, index_size_bytes: 0, last_updated: null, embed_model: '', sources: [] })
const documents = ref([])
const ingestText = ref('')
const ingestSource = ref('')
const ingestLanguage = ref('auto')
const searchQuery = ref('')
const searchResults = ref([])
const loading = ref(false)
const ingesting = ref(false)
const searching = ref(false)
const activeTab = ref('ingest') // 'ingest' | 'documents' | 'search'

// Confirm modal state
const confirmModal = ref({ show: false, title: '', message: '', action: null, destructive: false })

function showConfirm(title, message, action, destructive = true) {
  confirmModal.value = { show: true, title, message, action, destructive }
}

function confirmYes() {
  if (confirmModal.value.action) confirmModal.value.action()
  confirmModal.value.show = false
}

function confirmNo() {
  confirmModal.value.show = false
}

async function fetchStats() {
  try {
    const res = await authFetch(`${ADMIN_API}/admin/rag/stats`)
    if (res.ok) stats.value = await res.json()
  } catch {}
}

async function fetchDocuments() {
  loading.value = true
  try {
    const res = await authFetch(`${ADMIN_API}/admin/rag/documents?limit=100`)
    if (res.ok) documents.value = await res.json()
  } catch {}
  loading.value = false
}

async function ingest() {
  if (!ingestText.value.trim()) return
  ingesting.value = true
  try {
    const res = await authFetch(`${ADMIN_API}/admin/rag/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        texts: [ingestText.value],
        source: ingestSource.value || 'manual',
        language: ingestLanguage.value,
      }),
    })
    if (res.ok) {
      const data = await res.json()
      const langLabel = data.detected_language ? ` (${data.detected_language.toUpperCase()})` : ''
      window.dispatchEvent(new CustomEvent('aziza-toast', {
        detail: { type: 'success', message: `Ingested ${data.ingested} chunks${langLabel}` },
      }))
      ingestText.value = ''
      await fetchStats()
      await fetchDocuments()
    }
  } catch {}
  ingesting.value = false
}

async function searchRAG() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const res = await authFetch(`${ADMIN_API}/admin/rag/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: searchQuery.value, top_k: 5 }),
    })
    if (res.ok) {
      const data = await res.json()
      searchResults.value = data.results
    }
  } catch {}
  searching.value = false
}

async function deleteDocument(docId) {
  try {
    await authFetch(`${ADMIN_API}/admin/rag/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' })
    documents.value = documents.value.filter(d => d.doc_id !== docId)
    await fetchStats()
  } catch {}
}

function deleteSource(source) {
  const count = docsBySource.value[source]?.length || 0
  showConfirm(
    'Delete Source',
    `This will permanently remove all ${count} chunks from source "${source}". This action cannot be undone.`,
    async () => {
      try {
        await authFetch(`${ADMIN_API}/admin/rag/source/${encodeURIComponent(source)}`, { method: 'DELETE' })
        await fetchStats()
        await fetchDocuments()
        window.dispatchEvent(new CustomEvent('aziza-toast', {
          detail: { type: 'success', message: `Deleted source "${source}"` },
        }))
      } catch {}
    }
  )
}

function clearIndex() {
  showConfirm(
    'Clear Entire Index',
    `This will permanently delete all ${stats.value.doc_count} chunks from the knowledge base. This action cannot be undone.`,
    async () => {
      await authFetch(`${ADMIN_API}/admin/rag/clear`, { method: 'DELETE' })
      documents.value = []
      searchResults.value = []
      await fetchStats()
      window.dispatchEvent(new CustomEvent('aziza-toast', {
        detail: { type: 'success', message: 'RAG index cleared' },
      }))
    }
  )
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function truncate(text, len = 120) {
  return text.length > len ? text.slice(0, len) + '...' : text
}

// Group documents by source
const docsBySource = computed(() => {
  const groups = {}
  for (const doc of documents.value) {
    const src = doc.source || 'unknown'
    if (!groups[src]) groups[src] = []
    groups[src].push(doc)
  }
  return groups
})

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'documents' && documents.value.length === 0) fetchDocuments()
}

onMounted(fetchStats)
</script>

<template>
  <div>
    <!-- Confirm Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="confirmModal.show" class="modal-overlay" @click.self="confirmNo">
          <div class="modal-box">
            <div class="modal-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h3 class="modal-title">{{ confirmModal.title }}</h3>
            <p class="modal-message">{{ confirmModal.message }}</p>
            <div class="modal-actions">
              <button class="modal-btn modal-cancel" @click="confirmNo">Cancel</button>
              <button
                :class="['modal-btn', confirmModal.destructive ? 'modal-danger' : 'modal-confirm']"
                @click="confirmYes"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="stat-item">
        <span class="stat-label">Chunks</span>
        <span class="stat-val">{{ stats.doc_count }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Sources</span>
        <span class="stat-val">{{ stats.source_count }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Index Size</span>
        <span class="stat-val">{{ formatBytes(stats.index_size_bytes) }}</span>
      </div>
      <div v-if="stats.last_updated" class="stat-item">
        <span class="stat-label">Updated</span>
        <span class="stat-val dim">{{ new Date(stats.last_updated).toLocaleString() }}</span>
      </div>
      <div v-if="stats.embed_model" class="stat-item">
        <span class="stat-label">Model</span>
        <span class="stat-val dim">{{ stats.embed_model.split('/').pop() }}</span>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'ingest' }]" @click="switchTab('ingest')">Ingest</button>
      <button :class="['tab', { active: activeTab === 'documents' }]" @click="switchTab('documents')">
        Documents <span v-if="stats.doc_count" class="badge">{{ stats.doc_count }}</span>
      </button>
      <button :class="['tab', { active: activeTab === 'search' }]" @click="switchTab('search')">Search</button>
    </div>

    <!-- Ingest Tab -->
    <div v-if="activeTab === 'ingest'" class="tab-content">
      <div class="ingest-meta">
        <input v-model="ingestSource" placeholder="Source name (e.g. docs, faq)" class="meta-input" />
        <select v-model="ingestLanguage" class="meta-select">
          <option value="auto">Auto-detect</option>
          <option value="en">EN</option>
          <option value="ru">RU</option>
          <option value="uz">UZ</option>
        </select>
      </div>
      <textarea
        v-model="ingestText"
        rows="5"
        placeholder="Paste text to ingest into the knowledge base...&#10;&#10;Text will be automatically chunked and embedded."
        class="ingest-input"
      />
      <div class="btn-row">
        <button @click="ingest" :disabled="ingesting || !ingestText.trim()" class="ingest-btn">
          {{ ingesting ? 'Ingesting...' : 'Ingest Text' }}
        </button>
        <button @click="clearIndex" class="clear-btn" :disabled="!stats.doc_count">Clear All</button>
      </div>
    </div>

    <!-- Documents Tab -->
    <div v-if="activeTab === 'documents'" class="tab-content">
      <div v-if="loading" class="empty">Loading documents...</div>
      <div v-else-if="!documents.length" class="empty">No documents in the index yet.</div>
      <div v-else class="doc-list">
        <div v-for="(docs, source) in docsBySource" :key="source" class="source-group">
          <div class="source-header">
            <span class="source-name">{{ source }}</span>
            <span class="source-count">{{ docs.length }} chunks</span>
            <button @click="deleteSource(source)" class="source-delete" title="Delete all from this source">x</button>
          </div>
          <div v-for="doc in docs.slice(0, 10)" :key="doc.doc_id" class="doc-item">
            <div class="doc-text">{{ truncate(doc.text) }}</div>
            <div class="doc-meta">
              <span class="lang-badge">{{ doc.language.toUpperCase() }}</span>
              <span v-if="doc.created_at" class="doc-date">{{ new Date(doc.created_at).toLocaleDateString() }}</span>
              <button @click="deleteDocument(doc.doc_id)" class="doc-delete" title="Delete chunk">x</button>
            </div>
          </div>
          <div v-if="docs.length > 10" class="more-indicator">
            ... and {{ docs.length - 10 }} more chunks
          </div>
        </div>
      </div>
    </div>

    <!-- Search Tab -->
    <div v-if="activeTab === 'search'" class="tab-content">
      <div class="search-bar">
        <input
          v-model="searchQuery"
          placeholder="Test a search query..."
          class="search-input"
          @keydown.enter="searchRAG"
        />
        <button @click="searchRAG" :disabled="searching || !searchQuery.trim()" class="search-btn">
          {{ searching ? '...' : 'Search' }}
        </button>
      </div>
      <div v-if="searchResults.length" class="search-results">
        <div v-for="(r, i) in searchResults" :key="i" class="result-item">
          <div class="result-header">
            <span class="result-rank">#{{ i + 1 }}</span>
            <span class="result-score">{{ (r.score * 100).toFixed(1) }}%</span>
            <span class="lang-badge">{{ r.language.toUpperCase() }}</span>
            <span class="result-source">{{ r.source }}</span>
          </div>
          <div class="result-text">{{ r.text }}</div>
        </div>
      </div>
      <div v-else-if="searchQuery && !searching" class="empty">No results. Try ingesting some documents first.</div>
    </div>
  </div>
</template>

<style scoped>
/* Confirm Modal */
.modal-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.modal-box {
  background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: 16px; padding: 1.75rem; width: 400px; max-width: 90vw;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  display: flex; flex-direction: column; align-items: center; text-align: center;
}
.modal-icon {
  width: 48px; height: 48px; border-radius: 50%;
  background: rgba(239, 68, 68, 0.1); display: flex; align-items: center;
  justify-content: center; margin-bottom: 1rem;
}
.modal-title {
  font-size: 1rem; font-weight: 700; color: var(--text-primary);
  margin: 0 0 0.5rem;
}
.modal-message {
  font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5;
  margin: 0 0 1.5rem;
}
.modal-actions { display: flex; gap: 0.75rem; width: 100%; }
.modal-btn {
  flex: 1; padding: 0.55rem 1rem; border-radius: 10px; font-size: 0.82rem;
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
.modal-confirm {
  background: linear-gradient(135deg, #14b8a6, #0891b2); color: white;
}

/* Modal transitions */
.modal-enter-active { transition: opacity 0.2s ease; }
.modal-leave-active { transition: opacity 0.15s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-box { animation: modal-pop 0.2s ease; }
@keyframes modal-pop {
  0% { transform: scale(0.9); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

.stats-row { display: flex; gap: 1.2rem; margin-bottom: 0.75rem; flex-wrap: wrap; }
.stat-item { display: flex; flex-direction: column; gap: 0.1rem; }
.stat-label { font-size: 0.6rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); }
.stat-val { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }
.stat-val.dim { color: var(--text-secondary); font-weight: 400; font-size: 0.75rem; }

/* Tabs */
.tabs { display: flex; gap: 0.25rem; margin-bottom: 0.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
.tab {
  background: none; border: none; color: var(--text-muted); font-size: 0.78rem; font-weight: 500;
  padding: 0.35rem 0.75rem; border-radius: 6px; cursor: pointer; transition: all 0.15s;
  display: flex; align-items: center; gap: 0.35rem;
}
.tab:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.tab.active { color: #14b8a6; background: rgba(20,184,166,0.08); font-weight: 600; }
.badge {
  background: rgba(20,184,166,0.15); color: #14b8a6; font-size: 0.65rem; font-weight: 700;
  padding: 0.1rem 0.4rem; border-radius: 10px;
}

.tab-content { min-height: 120px; }

/* Ingest */
.ingest-meta { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.meta-input {
  flex: 1; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px;
  padding: 0.4rem 0.65rem; font-size: 0.78rem; color: var(--text-primary); outline: none;
  font-family: inherit;
}
.meta-input::placeholder { color: var(--text-muted); }
.meta-input:focus { border-color: rgba(20,184,166,0.3); }
.meta-select {
  background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px;
  padding: 0.4rem 0.5rem; font-size: 0.78rem; color: var(--text-primary); outline: none;
  cursor: pointer;
}

.ingest-input {
  width: 100%; background: var(--bg-input); border: 1px solid var(--border); border-radius: 10px;
  padding: 0.65rem 0.85rem; font-size: 0.8rem; color: var(--text-primary); resize: vertical;
  outline: none; font-family: inherit; transition: border-color 0.2s; margin-bottom: 0.6rem;
  min-height: 80px;
}
.ingest-input::placeholder { color: var(--text-muted); }
.ingest-input:focus { border-color: rgba(20,184,166,0.3); }

.btn-row { display: flex; gap: 0.5rem; }
.ingest-btn {
  background: linear-gradient(135deg, #14b8a6, #0891b2); border: none; color: white;
  font-size: 0.78rem; font-weight: 600; padding: 0.45rem 1.1rem; border-radius: 8px;
  cursor: pointer; transition: all 0.15s; box-shadow: 0 2px 8px rgba(20,184,166,0.2);
}
.ingest-btn:hover { box-shadow: 0 4px 12px rgba(20,184,166,0.3); }
.ingest-btn:disabled { opacity: 0.3; cursor: not-allowed; box-shadow: none; }
.clear-btn {
  background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.15);
  color: #f87171; font-size: 0.78rem; font-weight: 500; padding: 0.45rem 1.1rem;
  border-radius: 8px; cursor: pointer; transition: all 0.15s;
}
.clear-btn:hover { background: rgba(239,68,68,0.15); border-color: rgba(239,68,68,0.3); }
.clear-btn:disabled { opacity: 0.3; cursor: not-allowed; }

/* Documents */
.doc-list { max-height: 350px; overflow-y: auto; }
.source-group { margin-bottom: 0.75rem; }
.source-header {
  display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0.5rem;
  background: var(--bg-tertiary); border-radius: 6px; margin-bottom: 0.35rem;
}
.source-name { font-size: 0.78rem; font-weight: 600; color: #14b8a6; }
.source-count { font-size: 0.65rem; color: var(--text-muted); }
.source-delete {
  margin-left: auto; background: none; border: none; color: #f87171; cursor: pointer;
  font-size: 0.75rem; font-weight: 700; padding: 0.1rem 0.4rem; border-radius: 4px;
  transition: background 0.15s;
}
.source-delete:hover { background: rgba(239,68,68,0.15); }

.doc-item {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;
  padding: 0.35rem 0.5rem; border-bottom: 1px solid var(--border);
}
.doc-text { font-size: 0.73rem; color: var(--text-secondary); flex: 1; line-height: 1.4; }
.doc-meta { display: flex; align-items: center; gap: 0.35rem; flex-shrink: 0; }
.lang-badge {
  font-size: 0.55rem; font-weight: 700; background: rgba(20,184,166,0.12); color: #14b8a6;
  padding: 0.1rem 0.35rem; border-radius: 4px; letter-spacing: 0.05em;
}
.doc-date { font-size: 0.6rem; color: var(--text-muted); }
.doc-delete {
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  font-size: 0.7rem; padding: 0.1rem 0.3rem; border-radius: 4px; transition: all 0.15s;
}
.doc-delete:hover { color: #f87171; background: rgba(239,68,68,0.1); }
.more-indicator { font-size: 0.7rem; color: var(--text-muted); padding: 0.3rem 0.5rem; font-style: italic; }

/* Search */
.search-bar { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
.search-input {
  flex: 1; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px;
  padding: 0.45rem 0.75rem; font-size: 0.8rem; color: var(--text-primary); outline: none;
  font-family: inherit;
}
.search-input::placeholder { color: var(--text-muted); }
.search-input:focus { border-color: rgba(20,184,166,0.3); }
.search-btn {
  background: linear-gradient(135deg, #14b8a6, #0891b2); border: none; color: white;
  font-size: 0.78rem; font-weight: 600; padding: 0.45rem 1rem; border-radius: 8px;
  cursor: pointer; min-width: 70px;
}
.search-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.search-results { max-height: 300px; overflow-y: auto; }
.result-item {
  padding: 0.5rem; border: 1px solid var(--border); border-radius: 8px;
  margin-bottom: 0.4rem; background: var(--bg-secondary);
}
.result-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem; }
.result-rank { font-size: 0.7rem; font-weight: 700; color: #14b8a6; }
.result-score {
  font-size: 0.65rem; font-weight: 600; background: rgba(20,184,166,0.1); color: #14b8a6;
  padding: 0.1rem 0.4rem; border-radius: 10px;
}
.result-source { font-size: 0.65rem; color: var(--text-muted); margin-left: auto; }
.result-text { font-size: 0.75rem; color: var(--text-secondary); line-height: 1.5; }

.empty { font-size: 0.78rem; color: var(--text-muted); text-align: center; padding: 1.5rem; }
</style>
