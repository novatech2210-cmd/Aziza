<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authFetch } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

const router = useRouter()
const theme = useThemeStore()

const PERSONA_API_BASE = import.meta.env.VITE_PERSONA_API_URL || '/api/personas'

const personas = ref([])
const selectedPersona = ref(null)
const isEditing = ref(false)

const draftPersona = ref(null)

function selectPersona(p) {
  selectedPersona.value = p
  isEditing.value = false
}

function startEdit() {
  draftPersona.value = JSON.parse(JSON.stringify(selectedPersona.value))
  isEditing.value = true
}

function cancelEdit() {
  isEditing.value = false
  draftPersona.value = null
}

async function savePersona() {
  try {
    const res = await authFetch(`${PERSONA_API_BASE}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draftPersona.value)
    })
    if (res.ok) {
      const saved = await res.json()
      const index = personas.value.findIndex(p => p.id === saved.id)
      if (index !== -1) {
        personas.value[index] = saved
      } else {
        personas.value.push(saved)
      }
      selectedPersona.value = saved
      isEditing.value = false
      window.dispatchEvent(new CustomEvent('aziza-toast', {
        detail: { type: 'success', message: 'Persona saved successfully' },
      }))
    } else {
      throw new Error('API Error')
    }
  } catch(err) {
    window.dispatchEvent(new CustomEvent('aziza-toast', {
      detail: { type: 'error', message: 'Failed to save persona' },
    }))
  }
}

async function deleteSelectedPersona() {
  if (!selectedPersona.value || !confirm('Are you sure you want to delete this persona?')) return
  try {
    const res = await authFetch(`${PERSONA_API_BASE}/${selectedPersona.value.id}`, { method: 'DELETE' })
    if (res.ok) {
      personas.value = personas.value.filter(p => p.id !== selectedPersona.value.id)
      selectedPersona.value = personas.value.length ? personas.value[0] : null
      isEditing.value = false
      window.dispatchEvent(new CustomEvent('aziza-toast', {
        detail: { type: 'success', message: 'Persona deleted successfully' },
      }))
    }
  } catch(err) {
    window.dispatchEvent(new CustomEvent('aziza-toast', {
      detail: { type: 'error', message: 'Failed to delete persona' },
    }))
  }
}

function createNew() {
  const newP = {
    id: 'p_' + Date.now(),
    name: 'New Persona',
    language: 'ru_colloquial',
    tone: 'Neutral',
    systemPrompt: '',
    isActive: false
  }
  personas.value.push(newP)
  selectPersona(newP)
  startEdit()
}

const testMessage = ref('')
const testResponse = ref(null)
const isTesting = ref(false)
const API_BASE = 'http://localhost:8020'

async function sendTestMessage() {
  if (!testMessage.value.trim()) return
  
  isTesting.value = true
  testResponse.value = null
  
  try {
    const res = await authFetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: testMessage.value, max_tokens: 150 })
    })
    
    if (!res.ok) throw new Error('API request failed')
    
    const data = await res.json()
    testResponse.value = data
  } catch (err) {
    console.error(err)
    testResponse.value = { error: err.message || 'Failed to connect to backend API' }
  } finally {
    isTesting.value = false
  }
}

async function fetchPersonas() {
  try {
    const res = await authFetch(`${PERSONA_API_BASE}`)
    if (res.ok) {
      personas.value = await res.json()
      if (personas.value.length > 0 && !selectedPersona.value) {
        selectPersona(personas.value[0])
      }
    }
  } catch (err) {
    console.error('Failed to fetch personas', err)
  }
}

onMounted(() => {
  fetchPersonas()
})
</script>

<template>
  <div class="persona-page">
    <!-- Header -->
    <header class="admin-header">
      <div class="header-left">
        <router-link to="/admin" class="back-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back to Admin
        </router-link>
        <div class="header-title">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 00-3-3.87" />
            <path d="M16 3.13a4 4 0 010 7.75" />
          </svg>
          <h1>Character Management</h1>
        </div>
      </div>
      <div class="header-actions">
        <button class="theme-toggle" @click="theme.toggle()" :title="theme.isDark ? 'Switch to light mode' : 'Switch to dark mode'">
          <svg v-if="theme.isDark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
        </button>
        <button class="primary-btn" @click="createNew">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          New Persona
        </button>
      </div>
    </header>

    <div class="layout-grid">
      <!-- Sidebar List -->
      <aside class="sidebar panel">
        <h3 class="panel-title">Your Personas</h3>
        <div class="persona-list">
          <div 
            v-for="p in personas" 
            :key="p.id" 
            :class="['persona-item', { active: selectedPersona?.id === p.id }]"
            @click="selectPersona(p)"
          >
            <div class="p-avatar">
              {{ p.name.charAt(0) }}
            </div>
            <div class="p-info">
              <h4>{{ p.name }}</h4>
              <span class="badge">{{ p.language }}</span>
            </div>
            <div v-if="p.isActive" class="active-dot" title="Currently Active in Production"></div>
          </div>
        </div>
      </aside>

      <!-- Main Editor -->
      <main class="editor panel" v-if="selectedPersona">
        <div class="editor-header">
          <h2 v-if="!isEditing">{{ selectedPersona.name }}</h2>
          <input v-else v-model="draftPersona.name" class="form-input text-xl font-bold" placeholder="Persona Name" />
          
          <div class="editor-actions">
            <template v-if="!isEditing">
              <button class="secondary-btn" @click="startEdit">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                Edit
              </button>
              <button class="secondary-btn" style="color: #ef4444; border-color: #ef4444;" @click="deleteSelectedPersona">Delete</button>
            </template>
            <template v-else>
              <button class="secondary-btn" @click="cancelEdit">Cancel</button>
              <button class="primary-btn" @click="savePersona">Save</button>
            </template>
          </div>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>Language Adapter</label>
            <select v-if="isEditing" v-model="draftPersona.language" class="form-select">
              <option value="ru_professional">Russian (Professional)</option>
              <option value="ru_colloquial">Russian (Colloquial)</option>
              <option value="uz_latin">Uzbek (Latin)</option>
              <option value="uz_cyrillic">Uzbek (Cyrillic)</option>
              <option value="en_core">English (Core)</option>
            </select>
            <div v-else class="read-value">{{ selectedPersona.language }}</div>
          </div>

          <div class="form-group">
            <label>Emotional Tone</label>
            <select v-if="isEditing" v-model="draftPersona.tone" class="form-select">
              <option value="Formal">Formal & Professional</option>
              <option value="Casual">Casual & Friendly</option>
              <option value="Empathetic">Empathetic</option>
              <option value="Neutral">Neutral</option>
            </select>
            <div v-else class="read-value">{{ selectedPersona.tone }}</div>
          </div>

          <div class="form-group full-width">
            <label>System Prompt</label>
            <p class="help-text">This exact prompt will be injected into the LMGen cache during initialization.</p>
            <textarea 
              v-if="isEditing" 
              v-model="draftPersona.systemPrompt" 
              class="form-textarea" 
              rows="6"
              placeholder="Ты — Азиза..."
            ></textarea>
            <div v-else class="read-value prompt-preview">{{ selectedPersona.systemPrompt }}</div>
          </div>
        </div>

        <div class="test-section" v-if="!isEditing">
          <h3>Simulate Persona</h3>
          <p>Test this character's responses using the current fine-tuned model before deploying to production.</p>
          <div class="test-chat">
            <input type="text" v-model="testMessage" @keyup.enter="sendTestMessage" class="form-input" placeholder="Type a message to test..." :disabled="isTesting" />
            <button class="primary-btn" @click="sendTestMessage" :disabled="isTesting || !testMessage.trim()">
              <span v-if="isTesting">Sending...</span>
              <span v-else>Send</span>
            </button>
          </div>
          
          <div v-if="testResponse" class="test-response">
            <template v-if="testResponse.error">
              <p class="error-text">{{ testResponse.error }}</p>
            </template>
            <template v-else>
              <div class="response-text"><strong>Response:</strong> <span>{{ testResponse.response }}</span></div>
              <div class="response-meta">
                <span>⏱️ {{ testResponse.total_ms?.toFixed(1) }}ms</span>
                <span v-if="testResponse.has_cyrillic">✅ Cyrillic Detected</span>
                <span>Adapter: {{ testResponse.adapter }}</span>
              </div>
            </template>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.persona-page {
  min-height: 100vh;
  background: var(--bg-page);
  padding: 1.5rem;
}

/* Header Reused from AdminView */
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
  color: #14b8a6;
}

.header-title h1 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
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

/* Buttons */
.primary-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: linear-gradient(135deg, #14b8a6, #0891b2);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.primary-btn:hover {
  opacity: 0.9;
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border);
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.secondary-btn:hover {
  background: var(--bg-secondary);
}

/* Layout */
.layout-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 1.5rem;
  height: calc(100vh - 120px);
}

.panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-title {
  padding: 1.25rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
  margin: 0;
}

/* Sidebar */
.persona-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
}

.persona-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.persona-item:hover {
  background: var(--hover-overlay);
}

.persona-item.active {
  background: rgba(20, 184, 166, 0.1);
  border-color: rgba(20, 184, 166, 0.3);
}

.p-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #ec4899);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1rem;
}

.p-info h4 {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-primary);
  font-weight: 600;
}

.badge {
  font-size: 0.65rem;
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  margin-top: 0.2rem;
  display: inline-block;
}

.active-dot {
  width: 8px;
  height: 8px;
  background: #10b981;
  border-radius: 50%;
  margin-left: auto;
  box-shadow: 0 0 6px #10b981;
}

/* Editor */
.editor {
  padding: 2rem;
  overflow-y: auto;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.editor-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.editor-actions {
  display: flex;
  gap: 0.75rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group.full-width {
  grid-column: span 2;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.help-text {
  font-size: 0.75rem;
  color: var(--text-tertiary);
  margin: 0;
}

.form-input, .form-select, .form-textarea {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 0.9rem;
  transition: border-color 0.2s;
}

.form-input:focus, .form-select:focus, .form-textarea:focus {
  outline: none;
  border-color: #14b8a6;
}

.read-value {
  padding: 0.75rem;
  background: rgba(0,0,0,0.02);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 0.95rem;
  border: 1px dashed var(--border);
}

.prompt-preview {
  font-family: monospace;
  white-space: pre-wrap;
  line-height: 1.5;
  background: var(--bg-tertiary);
}

.test-section {
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 1px solid var(--border);
}

.test-section h3 {
  font-size: 1.1rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.test-section p {
  color: var(--text-secondary);
  font-size: 0.85rem;
  margin-bottom: 1rem;
}

.test-chat {
  display: flex;
  gap: 1rem;
}

.test-chat .form-input {
  flex: 1;
}

.coming-soon {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #ef4444 !important;
  font-style: italic;
}

.test-response {
  margin-top: 1.5rem;
  padding: 1rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.error-text {
  color: #ef4444 !important;
  margin: 0 !important;
}

.response-text {
  color: var(--text-primary);
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
  line-height: 1.5;
}

.response-meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.75rem;
  color: var(--text-tertiary);
}
</style>
