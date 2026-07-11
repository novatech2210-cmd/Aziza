<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, authFetch } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useThemeStore } from '../stores/theme'
import { useVoiceRecorder } from '../composables/useVoiceRecorder'
import { useVoiceChat } from '../composables/useVoiceChat'
import { useAudioDevices } from '../composables/useAudioDevices'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import python from 'highlight.js/lib/languages/python'
import typescript from 'highlight.js/lib/languages/typescript'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import bash from 'highlight.js/lib/languages/bash'
import yaml from 'highlight.js/lib/languages/yaml'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('json', json)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('yaml', yaml)

// Configure marked for markdown rendering
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      try { return hljs.highlight(code, { language: lang }).value } catch {}
    }
    try { return hljs.highlightAuto(code).value } catch {}
    return code
  },
})

const auth = useAuthStore()
const chat = useChatStore()
const theme = useThemeStore()
const router = useRouter()
const voice = useVoiceRecorder()
const voiceFullDuplex = useVoiceChat()
const audioDevices = useAudioDevices()

const inputText = ref('')
const messagesContainer = ref(null)
const sidebarOpen = ref(true)
const imageFile = ref(null)
const userMenuOpen = ref(false)
const userTier = ref(auth.user?.tier || 'free')
const searchQuery = ref('')
const searchOpen = ref(false)

const AUTH_API = import.meta.env.VITE_AUTH_API_URL || '/api'

async function fetchTier() {
  try {
    const res = await authFetch(`${AUTH_API}/me/tier`)
    if (res.ok) {
      const data = await res.json()
      userTier.value = data.tier
    }
  } catch {}
}

const modes = [
  { id: 'text', label: 'Text to Text', icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
  { id: 'voice-text', label: 'Voice to Text', icon: 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m-4 0h8M12 3a3 3 0 00-3 3v4a3 3 0 006 0V6a3 3 0 00-3-3z' },
  { id: 'voice-voice', label: 'Voice to Voice', icon: 'M8 12h.01M12 12h.01M16 12h.01M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 00-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0020 4.77 5.07 5.07 0 0019.91 1S18.73.65 16 2.48a13.38 13.38 0 00-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 005 4.77a5.44 5.44 0 00-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 009 18.13V22' },
  { id: 'image-text', label: 'Image to Text', icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z', soon: true },
]

function closeUserMenu(e) {
  if (userMenuOpen.value && !e.target.closest('.user-menu-wrapper')) {
    userMenuOpen.value = false
  }
}

onMounted(() => {
  chat.connect(auth.user?.id)
  chat.loadHistoryFromServer()
  fetchTier()
  document.addEventListener('click', closeUserMenu)
})

onUnmounted(() => {
  chat.disconnect()
  document.removeEventListener('click', closeUserMenu)
})

watch(
  () => chat.messages.length,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  }
)

watch(
  () => chat.messages[chat.messages.length - 1]?.content,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  }
)

function sendMessage() {
  const text = inputText.value.trim()
  if (!text || chat.isStreaming) return
  chat.sendMessage(text)
  inputText.value = ''
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function handleImageUpload(e) {
  const file = e.target.files?.[0]
  if (file) {
    imageFile.value = file
  }
}

async function toggleRecording() {
  if (chat.selectedMode === 'voice-voice') {
    if (voiceFullDuplex.isConnected.value) {
      voiceFullDuplex.disconnect()
    } else {
      await voiceFullDuplex.connect(audioDevices.selectedDeviceId.value)
    }
    return
  }

  if (voice.isRecording.value) {
    await voice.stop()
    if (voice.finalText.value.trim()) {
      chat.sendMessage(voice.finalText.value.trim())
      voice.reset()
    }
  } else {
    voice.reset()
    await voice.start(chat.selectedLanguage, audioDevices.selectedDeviceId.value)
  }
}

watch([() => voice.errorMessage.value, () => voiceFullDuplex.errorMessage.value], ([msg1, msg2]) => {
  const msg = msg1 || msg2
  if (msg) {
    window.dispatchEvent(new CustomEvent('aziza-toast', {
      detail: { type: 'error', message: `Voice: ${msg}` },
    }))
  }
})

const isVoiceMode = computed(() => chat.selectedMode === 'voice-text' || chat.selectedMode === 'voice-voice')

watch(isVoiceMode, (voiceMode) => {
  if (voiceMode && audioDevices.permissionState.value === 'prompt') {
    audioDevices.requestPermission()
  }
})

const filteredSessions = computed(() => {
  if (!searchQuery.value.trim()) return chat.sessionHistory
  const q = searchQuery.value.toLowerCase()
  return chat.sessionHistory.filter(s =>
    s.preview?.toLowerCase().includes(q) ||
    s.messages?.some(m => m.content?.toLowerCase().includes(q))
  )
})

function renderMarkdown(content) {
  if (!content) return ''
  return marked.parse(content)
}

function copyCode(e) {
  const btn = e.target.closest('.code-copy-btn')
  if (!btn) return
  const block = btn.closest('.code-block-wrapper')
  if (!block) return
  const code = block.querySelector('code')?.textContent || ''
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = 'Copied!'
    setTimeout(() => { btn.textContent = 'Copy' }, 1500)
  })
}

function exportConversation() {
  const lines = []
  lines.push(`# AZIZA Conversation`)
  lines.push(`Date: ${new Date().toLocaleString()}`)
  lines.push(`Language: ${chat.selectedLanguage}`)
  lines.push(`Mode: ${chat.selectedMode}`)
  lines.push('')
  for (const msg of chat.messages) {
    const role = msg.role === 'assistant' ? 'AZIZA' : 'You'
    const time = new Date(msg.timestamp).toLocaleTimeString()
    lines.push(`### ${role} (${time})`)
    lines.push('')
    lines.push(msg.content)
    lines.push('')
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `aziza-chat-${chat.sessionId.slice(0, 8)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function logout() {
  chat.disconnect()
  auth.logout()
}

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function getInitials(name) {
  return (name || 'U')[0].toUpperCase()
}
</script>

<template>
  <div class="chat-layout">
    <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
      <div class="sidebar-inner">
        <div class="sidebar-logo">
          <div class="logo-mark">
            <svg width="28" height="28" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="10" fill="url(#sg)" />
              <path d="M14 32L24 16L34 32H14Z" fill="white" opacity="0.9" />
              <defs><linearGradient id="sg" x1="0" y1="0" x2="48" y2="48"><stop stop-color="#14b8a6"/><stop offset="1" stop-color="#0891b2"/></linearGradient></defs>
            </svg>
          </div>
          <span class="logo-name">AZIZA</span>
        </div>

        <button @click="chat.newSession()" class="new-chat-btn">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Chat
        </button>

        <div class="sidebar-section">
          <p class="section-label">Mode</p>
          <div class="mode-list">
            <button
              v-for="mode in modes"
              :key="mode.id"
              @click="!mode.soon && chat.setMode(mode.id)"
              :class="['mode-btn', { active: chat.selectedMode === mode.id, disabled: mode.soon }]"
              :disabled="mode.soon"
            >
              <svg class="mode-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path :d="mode.icon" />
              </svg>
              <span>{{ mode.label }}</span>
              <span v-if="mode.soon" class="soon-badge">Soon</span>
            </button>
          </div>
        </div>

        <div v-if="chat.detectedLanguage" class="sidebar-section">
          <div class="detected-lang">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
            <span>Detected: <strong>{{ chat.detectedLanguage.language?.toUpperCase() }}</strong></span>
            <span v-if="chat.detectedLanguage.is_mixed" class="mixed-badge">Mixed</span>
          </div>
        </div>

        <div class="sidebar-section history-section">
          <div class="history-header">
            <p class="section-label">History</p>
            <div class="history-actions">
              <button @click="searchOpen = !searchOpen" class="sidebar-icon-btn" title="Search">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
              </button>
              <button @click="exportConversation" class="sidebar-icon-btn" title="Export" :disabled="!chat.messages.length">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
              </button>
            </div>
          </div>
          <div v-if="searchOpen" class="history-search">
            <input v-model="searchQuery" placeholder="Search conversations..." class="search-input" />
          </div>
          <div class="history-list">
            <div
              v-for="session in filteredSessions"
              :key="session.id"
              :class="['history-item', { active: chat.sessionId === session.id }]"
              @click="chat.loadSession(session)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
              </svg>
              <span>{{ session.preview }}</span>
              <button class="history-delete" @click.stop="chat.deleteSession(session.id)" title="Delete">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <p v-if="!filteredSessions?.length" class="no-history">{{ searchQuery ? 'No matches found' : 'No previous chats' }}</p>
          </div>
        </div>

        <div class="sidebar-footer">
          <div class="user-menu-wrapper">
            <button @click="userMenuOpen = !userMenuOpen" class="user-row-btn">
              <div class="user-avatar">{{ getInitials(auth.user?.username) }}</div>
              <div class="user-info">
                <span class="username">{{ auth.user?.username }}</span>
                <span :class="['tier-badge', userTier]">{{ userTier.toUpperCase() }}</span>
              </div>
              <svg class="chevron" :class="{ open: userMenuOpen }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg>
            </button>

            <transition name="dropdown">
              <div v-if="userMenuOpen" class="user-dropdown">
                <router-link v-if="auth.isAdmin" to="/admin" class="dropdown-item" @click="userMenuOpen = false">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                  Admin Panel
                </router-link>

                <router-link to="/usage" class="dropdown-item" @click="userMenuOpen = false">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
                  Usage & Plan
                </router-link>

                <button @click="theme.toggle()" class="dropdown-item">
                  <svg v-if="theme.isDark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
                  {{ theme.isDark ? 'Light Mode' : 'Dark Mode' }}
                </button>

                <div class="dropdown-divider" />

                <button @click="logout" class="dropdown-item danger">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
                  Sign Out
                </button>
              </div>
            </transition>
          </div>
        </div>
      </div>
    </aside>

    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false" />

    <main class="chat-main">
      <header class="chat-header">
        <button @click="sidebarOpen = !sidebarOpen" class="menu-btn">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        <div class="header-info">
          <span class="header-mode">
            {{ modes.find(m => m.id === chat.selectedMode)?.label || 'Chat' }}
          </span>
          <span v-if="chat.selectedLanguage === 'auto' && chat.detectedLanguage?.language" class="detected-badge">
            {{ chat.detectedLanguage.language.toUpperCase() }}
            <span v-if="chat.detectedLanguage.is_mixed" class="mixed-dot" />
          </span>
          <select 
            class="header-lang-select" 
            :value="chat.selectedLanguage" 
            @change="(e) => { chat.setLanguage(e.target.value); if (chat.selectedMode === 'voice-voice') voiceFullDuplex.updateLanguage(e.target.value); }"
          >
            <option value="auto">Auto-detect</option>
            <option value="en">English</option>
            <option value="ru">Russian</option>
            <option value="uz">Uzbek</option>
            <option value="ru_colloquial">RU Colloquial</option>
            <option value="ru_professional">RU Professional</option>
          </select>
        </div>

        <div class="connection-badge" :class="chat.connectionState">
          <span class="status-dot" />
          <template v-if="chat.connectionState === 'connected'">Connected</template>
          <template v-else-if="chat.connectionState === 'connecting'">Connecting...</template>
          <template v-else-if="chat.connectionState === 'reconnecting'">Reconnecting ({{ chat.reconnectAttempt }})...</template>
          <template v-else>Disconnected</template>
        </div>
      </header>

      <div ref="messagesContainer" class="messages-area">
        <div v-if="!chat.messages.length" class="empty-state">
          <div class="empty-logo">
            <svg width="64" height="64" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="14" fill="url(#eg)" opacity="0.15" />
              <path d="M14 32L24 16L34 32H14Z" fill="#14b8a6" opacity="0.5" />
              <defs><linearGradient id="eg" x1="0" y1="0" x2="48" y2="48"><stop stop-color="#14b8a6"/><stop offset="1" stop-color="#0891b2"/></linearGradient></defs>
            </svg>
          </div>
          <h2 class="empty-title">Start a conversation</h2>
          <p class="empty-subtitle">Ask AZIZA anything — type below or use voice input</p>

          <div class="quick-prompts">
            <button @click="inputText = 'What can you help me with?'" class="quick-btn">What can you help me with?</button>
            <button @click="inputText = 'Tell me about yourself'" class="quick-btn">Tell me about yourself</button>
            <button @click="inputText = 'Hello!'" class="quick-btn">Say hello</button>
          </div>
        </div>

        <template v-for="(msg, i) in chat.messages" :key="msg.id">
          <div :class="['msg-row', msg.role]">
            <div :class="['msg-avatar', msg.role]">
              <template v-if="msg.role === 'assistant'">
                <svg width="18" height="18" viewBox="0 0 48 48" fill="none">
                  <path d="M14 32L24 16L34 32H14Z" fill="white" />
                </svg>
              </template>
              <template v-else>
                {{ getInitials(auth.user?.username) }}
              </template>
            </div>

            <div :class="['msg-bubble', msg.role, { error: msg.isError }]">
              <div class="msg-header">
                <span class="msg-author">{{ msg.role === 'assistant' ? 'AZIZA' : auth.user?.username }}</span>
                <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div v-if="msg.role === 'assistant'" class="msg-content markdown-body" v-html="renderMarkdown(msg.content)" @click="copyCode"></div>
              <div v-else class="msg-content">
                <span>{{ msg.content }}</span>
              </div>
              <span v-if="msg.isStreaming" class="cursor-blink">|</span>
            </div>
          </div>
        </template>
      </div>

      <div class="input-area">
        <div v-if="isVoiceMode" class="voice-input-container">
          <!-- Permission denied state -->
          <div v-if="audioDevices.permissionState.value === 'denied'" class="permission-denied">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            <span>Microphone access denied</span>
            <button class="permission-retry-btn" @click="audioDevices.requestPermission()">Grant Access</button>
          </div>

          <template v-else>
            <!-- Device selector -->
            <div v-if="audioDevices.devices.value.length > 1" class="device-selector">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/></svg>
              <select
                :value="audioDevices.selectedDeviceId.value"
                @change="(e) => audioDevices.selectDevice(e.target.value)"
                class="device-select"
              >
                <option v-for="d in audioDevices.devices.value" :key="d.deviceId" :value="d.deviceId">
                  {{ d.label || 'Microphone ' + (audioDevices.devices.value.indexOf(d) + 1) }}
                </option>
              </select>
            </div>

            <div v-if="voice.partialText.value || voice.finalText.value" class="voice-transcript">
              <span class="transcript-label">{{ voice.state.value === 'done' ? 'Transcript' : 'Listening...' }}</span>
              <p class="transcript-text">{{ voice.partialText.value || voice.finalText.value }}</p>
            </div>

            <div class="voice-controls">
              <button
                @click="toggleRecording"
                :class="['mic-btn', voice.state.value]"
                :disabled="!chat.isConnected || voice.state.value === 'processing'"
              >
                <svg v-if="!voice.isRecording.value && !voiceFullDuplex.isConnecting.value" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
                  <path d="M19 10v2a7 7 0 01-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
                <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
                <div v-if="voice.isRecording.value" class="mic-pulse" :style="{ transform: `scale(${1 + voice.audioLevel.value * 3})` }" />
              </button>

              <span class="voice-state-label">
                <template v-if="voiceFullDuplex.isConnecting.value">Connecting...</template>
                <template v-else-if="voice.state.value === 'idle'">Tap to speak</template>
                <template v-else-if="voice.state.value === 'requesting'">Requesting mic...</template>
                <template v-else-if="voice.state.value === 'recording'">Recording — tap to stop</template>
                <template v-else-if="voice.state.value === 'processing'">Transcribing...</template>
                <template v-else-if="voice.state.value === 'done'">Sent!</template>
                <template v-else-if="voice.state.value === 'error'">{{ voice.errorMessage.value }}</template>
              </span>
            </div>
          </template>
        </div>

        <div v-else class="input-container">
          <label v-if="chat.selectedMode === 'image-text'" class="icon-btn">
            <input type="file" accept="image/*" @change="handleImageUpload" style="display:none" />
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </label>

          <textarea
            v-model="inputText"
            @keydown="handleKeydown"
            rows="1"
            placeholder="Message AZIZA..."
            class="chat-input"
            :disabled="!chat.isConnected"
          />

          <button
            v-if="chat.isStreaming"
            @click="chat.stopGeneration()"
            class="stop-btn"
            title="Stop generation"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
          </button>

          <button
            v-else
            @click="sendMessage"
            :disabled="!inputText.trim() || !chat.isConnected"
            :class="['send-btn', { active: inputText.trim() }]"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <div class="input-actions">
          <button
            v-if="!chat.isStreaming && chat.messages.length > 0"
            @click="chat.retryLastMessage()"
            class="action-btn"
            title="Retry last message"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>
            Retry
          </button>
          <p class="input-hint">
          <template v-if="chat.selectedMode === 'voice-voice'">Continuous full-duplex — tap mic to connect</template>
          <template v-else-if="isVoiceMode">Tap the microphone to start speaking</template>
          <template v-else>Press Enter to send, Shift+Enter for new line</template>
        </p>
        </div>
      </div>
    </main>

    <!-- Full-Duplex UI Overlay -->
    <transition name="fade">
      <div v-if="chat.selectedMode === 'voice-voice' && voiceFullDuplex.isConnected.value" class="voice-overlay">
        <div class="voice-overlay-content">
          <div class="voice-visualizer">
            <div class="orb-container">
              <div class="orb-outer" :style="{ transform: `scale(${1 + voiceFullDuplex.amplitude.value * 0.5})` }" />
              <div class="orb-inner" :class="{ speaking: voiceFullDuplex.assistantState.value === 'SPEAKING' }">
                <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
                  <path d="M14 32L24 16L34 32H14Z" fill="white" />
                </svg>
              </div>
            </div>
            <div class="waves">
              <div v-for="i in 3" :key="i" class="wave" :style="{ animationDelay: `${i * 0.2}s`, opacity: 0.1 + (voiceFullDuplex.amplitude.value * 0.5) }" />
            </div>
          </div>
          
          <h2 class="voice-title">{{ voiceFullDuplex.assistantState.value === 'SPEAKING' ? 'AZIZA is speaking...' : 'Listening...' }}</h2>
          
          <div class="voice-transcript-full">
            <p v-for="(s, i) in voiceFullDuplex.completedSentences.value.slice(-3)" :key="i" class="transcript-line old">{{ s }}</p>
            <p v-if="voiceFullDuplex.pendingSentence.value" class="transcript-line pending">{{ voiceFullDuplex.pendingSentence.value }}<span class="cursor">|</span></p>
          </div>

          <!-- Add latency telemetry display -->
          <div v-if="voiceFullDuplex.e2eMetrics.value.timeToFirstChunk > 0" class="voice-metrics">
            <span class="metric-chip" title="Voice↔Voice Latency">V↔V: {{ voiceFullDuplex.e2eMetrics.value.voiceToVoiceLatency }}ms</span>
            <span class="metric-chip" title="Time to first chunk">TTFC: {{ voiceFullDuplex.e2eMetrics.value.timeToFirstChunk }}ms</span>
            <span v-if="voiceFullDuplex.e2eMetrics.value.voiceToTextLatency > 0" class="metric-chip" title="Voice→Text Latency">V→T: {{ voiceFullDuplex.e2eMetrics.value.voiceToTextLatency }}ms</span>
          </div>

          <div class="voice-actions">
            <button @click="voiceFullDuplex.toggleMute()" :class="['action-btn', { muted: voiceFullDuplex.muted.value }]">
              <svg v-if="!voiceFullDuplex.muted.value" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
              <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V4a3 3 0 00-5.94-.6"/><path d="M17 16.95A7 7 0 015 12v-2m14 0v2a7 7 0 01-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            </button>
            <button @click="voiceFullDuplex.disconnect()" class="action-btn exit">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.chat-layout { display: flex; height: 100vh; background: var(--bg-page); overflow: hidden; transition: background 0.3s; }
.sidebar { width: 280px; flex-shrink: 0; background: var(--bg-primary); border-right: 1px solid var(--border); transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), background 0.3s; overflow: hidden; z-index: 40; }
.sidebar.collapsed { width: 0; border-right: none; }
.sidebar-inner { display: flex; flex-direction: column; height: 100%; width: 280px; }
.sidebar-overlay { display: none; }
.sidebar-logo { display: flex; align-items: center; gap: 0.75rem; padding: 1.25rem; }
.logo-mark { flex-shrink: 0; filter: drop-shadow(0 0 8px rgba(20, 184, 166, 0.3)); }
.logo-name { font-size: 1.25rem; font-weight: 800; letter-spacing: 0.1em; background: linear-gradient(135deg, #14b8a6, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.new-chat-btn { display: flex; align-items: center; justify-content: center; gap: 0.5rem; margin: 0 1rem 0.75rem; padding: 0.65rem; border: 1px dashed var(--border-light); border-radius: 10px; background: transparent; color: var(--text-secondary); font-size: 0.85rem; font-weight: 500; cursor: pointer; transition: all 0.2s; }
.new-chat-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-glow); }
.sidebar-section { padding: 0.5rem 1rem; }
.section-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--text-tertiary); padding: 0 0.25rem; margin-bottom: 0.5rem; font-weight: 700; }
.mode-list { display: flex; flex-direction: column; gap: 2px; }
.mode-btn { display: flex; align-items: center; gap: 0.65rem; width: 100%; padding: 0.55rem 0.75rem; border: none; border-radius: 8px; background: transparent; color: var(--text-secondary); font-size: 0.82rem; cursor: pointer; transition: all 0.15s; text-align: left; }
.mode-btn:hover:not(.disabled) { background: var(--accent-glow); color: var(--text-primary); }
.mode-btn.active { background: var(--accent-glow); color: var(--accent); }
.mode-btn.disabled { opacity: 0.4; cursor: not-allowed; }
.mode-btn.disabled:hover { background: transparent; color: var(--text-secondary); }
.soon-badge { margin-left: auto; font-size: 0.58rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 0.12rem 0.45rem; border-radius: 6px; background: rgba(250, 204, 21, 0.12); color: #facc15; }
.mode-svg { flex-shrink: 0; opacity: 0.7; }
.mode-btn.active .mode-svg { opacity: 1; }
.detected-lang { display: flex; align-items: center; gap: 0.35rem; padding: 0.35rem 0.5rem; margin-top: 0.35rem; font-size: 0.68rem; color: var(--text-tertiary); background: var(--bg-tertiary); border-radius: 6px; }
.detected-lang svg { color: var(--accent); opacity: 0.7; flex-shrink: 0; }
.detected-lang strong { color: var(--accent); }
.mixed-badge, .layout-badge { font-size: 0.55rem; font-weight: 700; padding: 0.08rem 0.35rem; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.mixed-badge { background: rgba(168, 85, 247, 0.12); color: #a78bfa; }
.layout-badge { background: rgba(250, 204, 21, 0.12); color: #facc15; }
.history-section { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
.history-item { display: flex; align-items: center; gap: 0.5rem; width: 100%; padding: 0.5rem 0.65rem; border: none; border-radius: 8px; background: transparent; color: var(--text-tertiary); font-size: 0.8rem; text-align: left; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; transition: all 0.15s; }
.history-item:hover { background: var(--accent-glow); color: var(--text-secondary); }
.history-item.active { background: var(--accent-glow); color: var(--accent); border-left: 2px solid var(--accent); }
.history-item svg { flex-shrink: 0; opacity: 0.4; }
.history-item span { overflow: hidden; text-overflow: ellipsis; flex: 1; }
.history-delete { display: none; flex-shrink: 0; background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 2px; border-radius: 4px; transition: all 0.15s; }
.history-item:hover .history-delete { display: flex; }
.history-delete:hover { color: var(--danger); background: var(--danger-bg); }
.no-history { font-size: 0.75rem; color: var(--text-muted); padding: 0.5rem 0.25rem; }
.sidebar-footer { border-top: 1px solid var(--border); padding: 0.75rem 1rem; }
.user-menu-wrapper { position: relative; }
.user-row-btn { display: flex; align-items: center; gap: 0.65rem; width: 100%; padding: 0.5rem 0.5rem; background: transparent; border: 1px solid transparent; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
.user-row-btn:hover { background: var(--hover-overlay); border-color: var(--border); }
.user-avatar { width: 30px; height: 30px; border-radius: 8px; background: var(--accent-glow); display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; color: var(--accent); flex-shrink: 0; }
.user-info { display: flex; align-items: center; gap: 0.4rem; flex: 1; min-width: 0; }
.username { font-size: 0.8rem; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: left; }
.tier-badge { font-size: 0.55rem; font-weight: 800; letter-spacing: 0.06em; padding: 0.1rem 0.4rem; border-radius: 4px; text-transform: uppercase; flex-shrink: 0; }
.tier-badge.free { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.tier-badge.basic { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.tier-badge.pro { background: rgba(168, 85, 247, 0.15); color: #a78bfa; }
.tier-badge.enterprise { background: rgba(234, 179, 8, 0.15); color: #facc15; }
.chevron { color: var(--text-tertiary); flex-shrink: 0; transition: transform 0.2s; }
.chevron.open { transform: rotate(180deg); }
.user-dropdown { position: absolute; bottom: calc(100% + 0.5rem); left: 0; right: 0; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 12px; padding: 0.35rem; box-shadow: 0 8px 30px var(--shadow); z-index: 50; }
.dropdown-item { display: flex; align-items: center; gap: 0.6rem; width: 100%; padding: 0.6rem 0.75rem; border: none; border-radius: 8px; background: transparent; color: var(--text-secondary); font-size: 0.82rem; cursor: pointer; transition: all 0.15s; text-decoration: none; }
.dropdown-item:hover { background: var(--hover-overlay); color: var(--text-primary); }
.dropdown-item.danger { color: var(--danger); }
.dropdown-item.danger:hover { background: var(--danger-bg); }
.dropdown-divider { height: 1px; background: var(--border); margin: 0.25rem 0.5rem; }
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(8px); }
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--bg-page); transition: background 0.3s; }
.chat-header { display: flex; align-items: center; gap: 1rem; padding: 0.75rem 1.25rem; background: var(--bg-secondary); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border); z-index: 10; transition: background 0.3s, border-color 0.3s; }
.menu-btn { background: none; border: none; color: var(--text-tertiary); cursor: pointer; padding: 0.35rem; border-radius: 6px; display: flex; transition: all 0.15s; }
.menu-btn:hover { color: var(--text-primary); background: var(--accent-glow); }
.header-info { display: flex; align-items: center; gap: 0.75rem; }
.header-mode { font-size: 0.875rem; font-weight: 500; color: var(--text-secondary); }
.detected-badge { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 0.15rem 0.45rem; border-radius: 5px; background: rgba(20, 184, 166, 0.12); color: #14b8a6; border: 1px solid rgba(20, 184, 166, 0.25); display: inline-flex; align-items: center; gap: 0.3rem; }
.mixed-dot { width: 5px; height: 5px; border-radius: 50%; background: #f59e0b; }
.header-lang { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.05em; color: var(--accent); background: var(--accent-glow); padding: 0.2rem 0.5rem; border-radius: 4px; }
.header-lang-select { font-size: 0.75rem; font-weight: 600; color: var(--accent); background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 6px; padding: 0.25rem 0.5rem; cursor: pointer; outline: none; }
.header-lang-select:focus { border-color: var(--accent); }
.connection-badge { margin-left: auto; display: flex; align-items: center; gap: 0.4rem; font-size: 0.7rem; font-weight: 500; padding: 0.3rem 0.75rem; border-radius: 20px; letter-spacing: 0.02em; }
.connection-badge.connected { color: var(--success); background: rgba(34, 197, 94, 0.08); }
.connection-badge.disconnected { color: var(--danger); background: var(--danger-bg); }
.connection-badge.connecting, .connection-badge.reconnecting { color: var(--warning); background: rgba(234, 179, 8, 0.08); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; }
.connection-badge.connected .status-dot { background: var(--success); box-shadow: 0 0 8px rgba(34, 197, 94, 0.5); }
.connection-badge.disconnected .status-dot { background: var(--danger); box-shadow: 0 0 8px rgba(239, 68, 68, 0.5); }
.connection-badge.connecting .status-dot, .connection-badge.reconnecting .status-dot { background: var(--warning); box-shadow: 0 0 8px rgba(234, 179, 8, 0.5); animation: pulse-dot 1s infinite; }
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.messages-area { flex: 1; overflow-y: auto; padding: 1.5rem 1rem; display: flex; flex-direction: column; gap: 0.25rem; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; padding: 2rem; }
.empty-logo { margin-bottom: 1.5rem; opacity: 0.6; }
.empty-title { font-size: 1.5rem; font-weight: 600; color: var(--text-tertiary); margin-bottom: 0.5rem; }
.empty-subtitle { font-size: 0.9rem; color: var(--text-muted); }
.quick-prompts { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 2rem; justify-content: center; }
.quick-btn { padding: 0.5rem 1rem; border: 1px solid var(--border); border-radius: 20px; background: transparent; color: var(--text-tertiary); font-size: 0.8rem; cursor: pointer; transition: all 0.2s; }
.quick-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-glow); }
.msg-row { display: flex; gap: 0.75rem; padding: 0.75rem 0.5rem; max-width: 900px; width: 100%; margin: 0 auto; }
.msg-row.user { flex-direction: row-reverse; }
.msg-avatar { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 0.7rem; font-weight: 700; margin-top: 2px; }
.msg-avatar.assistant { background: linear-gradient(135deg, #14b8a6, #0891b2); box-shadow: 0 2px 8px rgba(20, 184, 166, 0.2); }
.msg-avatar.user { background: var(--accent-glow); color: var(--accent); }
.msg-bubble { max-width: 70%; min-width: 0; }
.msg-bubble.user { text-align: right; }
.msg-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem; }
.msg-row.user .msg-header { flex-direction: row-reverse; }
.msg-author { font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); }
.msg-time { font-size: 0.65rem; color: var(--text-muted); }
.msg-content { font-size: 0.9rem; line-height: 1.65; color: var(--text-primary); background: var(--msg-ai-bg); padding: 0.85rem 1.1rem; border-radius: 14px; border: 1px solid var(--msg-ai-border); white-space: pre-wrap; word-break: break-word; transition: background 0.3s, border-color 0.3s; }
.msg-row.user .msg-content { background: var(--msg-user-bg); border-color: var(--msg-user-border); }
.cursor-blink { color: var(--accent); animation: blink 0.8s step-end infinite; font-weight: 300; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
.input-area { padding: 0.75rem 1rem 1rem; background: var(--bg-secondary); backdrop-filter: blur(12px); border-top: 1px solid var(--border); transition: background 0.3s; }
.input-container { display: flex; align-items: flex-end; gap: 0.5rem; max-width: 900px; margin: 0 auto; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 14px; padding: 0.4rem 0.5rem; transition: border-color 0.2s, background 0.3s; }
.input-container:focus-within { border-color: rgba(20, 184, 166, 0.3); }
.icon-btn { flex-shrink: 0; color: var(--text-tertiary); cursor: pointer; padding: 0.5rem; border-radius: 8px; display: flex; transition: all 0.15s; }
.icon-btn:hover { color: var(--accent); background: var(--accent-glow); }
.chat-input { flex: 1; background: transparent; border: none; padding: 0.6rem 0.5rem; color: var(--text-primary); font-size: 0.9rem; resize: none; outline: none; font-family: inherit; min-height: 24px; max-height: 120px; line-height: 1.5; }
.chat-input::placeholder { color: var(--text-tertiary); }
.chat-input:disabled { opacity: 0.4; }
.send-btn { flex-shrink: 0; background: var(--bg-elevated); border: none; color: var(--text-tertiary); padding: 0.55rem; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.send-btn.active { background: linear-gradient(135deg, #14b8a6, #0891b2); color: white; box-shadow: 0 2px 8px rgba(20, 184, 166, 0.25); }
.send-btn:disabled { cursor: not-allowed; }
.input-hint { text-align: center; font-size: 0.65rem; color: var(--text-muted); margin-top: 0.5rem; }
.voice-input-container { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 0.5rem 0; width: 100%; }
.voice-transcript { width: 100%; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 12px; padding: 0.75rem 1rem; }
.transcript-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-tertiary); font-weight: 700; }
.transcript-text { font-size: 0.9rem; color: var(--text-primary); margin-top: 0.25rem; line-height: 1.5; min-height: 1.4em; }

/* Device selector */
.device-selector { width: 100%; display: flex; align-items: center; gap: 0.5rem; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 10px; padding: 0.35rem 0.65rem; color: var(--text-secondary); }
.device-select { flex: 1; background: transparent; border: none; color: var(--text-primary); font-size: 0.8rem; outline: none; cursor: pointer; padding: 0.2rem 0; }
.device-select option { background: var(--bg-secondary); color: var(--text-primary); }

/* Permission denied state */
.permission-denied { width: 100%; display: flex; align-items: center; gap: 0.75rem; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 12px; padding: 0.75rem 1rem; color: #fca5a5; font-size: 0.85rem; }
.permission-denied svg { flex-shrink: 0; }
.permission-denied span { flex: 1; }
.permission-retry-btn { flex-shrink: 0; background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); color: #fca5a5; font-size: 0.75rem; font-weight: 600; padding: 0.35rem 0.75rem; border-radius: 8px; cursor: pointer; transition: all 0.15s; }
.permission-retry-btn:hover { background: rgba(239, 68, 68, 0.3); }
.voice-controls { display: flex; align-items: center; gap: 1rem; }
.mic-btn { position: relative; width: 56px; height: 56px; border-radius: 50%; border: 2px solid var(--border-light); background: var(--bg-tertiary); color: var(--text-secondary); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.mic-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); background: var(--accent-glow); }
.mic-btn.recording { border-color: #ef4444; color: #ef4444; background: rgba(239, 68, 68, 0.1); animation: mic-glow 1.5s ease-in-out infinite; }
.mic-btn.processing { border-color: var(--warning); color: var(--warning); opacity: 0.7; cursor: wait; }
.mic-btn:disabled { opacity: 0.4; cursor: not-allowed; }
@keyframes mic-glow { 0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.3); } 50% { box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); } }
.mic-pulse { position: absolute; inset: -4px; border-radius: 50%; border: 2px solid rgba(239, 68, 68, 0.3); pointer-events: none; transition: transform 0.1s ease-out; }
.voice-state-label { font-size: 0.8rem; color: var(--text-tertiary); font-weight: 500; }

/* Voice Overlay Styles */
.voice-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: center; z-index: 100; }
.voice-overlay-content { display: flex; flex-direction: column; align-items: center; width: 100%; max-width: 600px; padding: 2rem; }
.voice-visualizer { position: relative; width: 240px; height: 240px; display: flex; align-items: center; justify-content: center; margin-bottom: 2rem; }
.orb-container { position: relative; z-index: 10; display: flex; align-items: center; justify-content: center; }
.orb-outer { position: absolute; width: 140px; height: 140px; border-radius: 50%; background: radial-gradient(circle, rgba(20,184,166,0.2) 0%, rgba(8,145,178,0) 70%); transition: transform 0.1s; }
.orb-inner { width: 100px; height: 100px; border-radius: 50%; background: linear-gradient(135deg, #14b8a6, #0891b2); display: flex; align-items: center; justify-content: center; box-shadow: 0 0 30px rgba(20,184,166,0.4); transition: all 0.3s; }
.orb-inner.speaking { box-shadow: 0 0 50px rgba(20,184,166,0.8); transform: scale(1.05); }
.waves { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; pointer-events: none; }
.wave { position: absolute; width: 100%; height: 100%; border-radius: 50%; border: 2px solid #14b8a6; animation: ripple 2s linear infinite; }
@keyframes ripple { 0% { transform: scale(0.5); opacity: 1; } 100% { transform: scale(1.5); opacity: 0; } }
.voice-title { font-size: 1.5rem; font-weight: 600; color: white; margin-bottom: 2rem; letter-spacing: 0.02em; }
.voice-transcript-full { width: 100%; height: 120px; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; text-align: center; margin-bottom: 3rem; }
.transcript-line { font-size: 1.1rem; line-height: 1.6; color: rgba(255,255,255,0.9); margin-bottom: 0.5rem; max-width: 90%; }
.transcript-line.old { color: rgba(255,255,255,0.5); font-size: 0.95rem; }
.transcript-line.pending { font-size: 1.25rem; font-weight: 500; }
.transcript-line .cursor { color: #14b8a6; animation: blink 0.8s step-end infinite; }
.voice-actions { display: flex; gap: 1.5rem; }
.action-btn { width: 56px; height: 56px; border-radius: 50%; border: none; background: rgba(255,255,255,0.1); color: white; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; backdrop-filter: blur(4px); }
.action-btn:hover { background: rgba(255,255,255,0.2); transform: scale(1.05); }
.action-btn.muted { background: rgba(239,68,68,0.2); color: #fca5a5; }
.action-btn.exit { background: rgba(239,68,68,0.8); }
.action-btn.exit:hover { background: #ef4444; }

.voice-metrics { display: flex; gap: 0.5rem; justify-content: center; margin-bottom: 2rem; flex-wrap: wrap; }
.metric-chip { background: rgba(20, 184, 166, 0.15); border: 1px solid rgba(20, 184, 166, 0.3); color: #5eead4; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }


/* Fade transition for overlay */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .sidebar { position: fixed; left: 0; top: 0; bottom: 0; box-shadow: 4px 0 30px var(--shadow); }
  .sidebar.collapsed { width: 0; box-shadow: none; }
  .sidebar-overlay { display: block; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 30; }
  .msg-bubble { max-width: 88%; }
  .msg-row { padding: 0.5rem 0.25rem; }
  .messages-area { padding: 0.75rem 0.5rem; }
  .input-area { padding: 0.5rem 0.5rem calc(0.75rem + env(safe-area-inset-bottom, 0px)); }
  .input-hint { display: none; }
  .header-info { gap: 0.5rem; }
  .connection-badge { font-size: 0.6rem; padding: 0.25rem 0.5rem; }
  .history-delete { display: flex; }
  .voice-input-container { padding: 0.25rem 0; gap: 0.5rem; }
  .device-selector { padding: 0.25rem 0.5rem; }
  .device-select { font-size: 0.75rem; }
  .permission-denied { padding: 0.5rem 0.75rem; font-size: 0.8rem; gap: 0.5rem; }
  .voice-controls { gap: 0.75rem; }
  .mic-btn { width: 48px; height: 48px; }
  .mic-btn svg { width: 20px; height: 20px; }
  .voice-state-label { font-size: 0.75rem; }
  .code-block-wrapper pre { padding: 0.75em; font-size: 0.78em; }
  .detected-badge { font-size: 0.6rem; padding: 0.1rem 0.35rem; }
  .chat-header { padding: 0.5rem 0.75rem; gap: 0.5rem; }
  .header-mode { font-size: 0.8rem; }
  .header-lang-select { font-size: 0.75rem; padding: 0.25rem 0.5rem; }
}

/* Markdown body styles for assistant messages */
.markdown-body { white-space: normal; }
.markdown-body p { margin: 0.5em 0; }
.markdown-body p:first-child { margin-top: 0; }
.markdown-body p:last-child { margin-bottom: 0; }
.markdown-body ul, .markdown-body ol { margin: 0.5em 0; padding-left: 1.5em; }
.markdown-body li { margin: 0.25em 0; }
.markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 { font-weight: 600; margin: 1em 0 0.5em; color: var(--text-primary); }
.markdown-body h1 { font-size: 1.2em; }
.markdown-body h2 { font-size: 1.1em; }
.markdown-body h3 { font-size: 1em; }
.markdown-body blockquote { border-left: 3px solid var(--accent); padding-left: 0.75em; margin: 0.5em 0; color: var(--text-secondary); }
.markdown-body code:not(.hljs) { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.85em; background: var(--bg-tertiary); padding: 0.15em 0.4em; border-radius: 4px; border: 1px solid var(--border); color: var(--accent); }
.markdown-body a { color: var(--accent); text-decoration: underline; }
.markdown-body table { border-collapse: collapse; margin: 0.75em 0; width: 100%; font-size: 0.85em; }
.markdown-body th, .markdown-body td { border: 1px solid var(--border); padding: 0.4em 0.75em; text-align: left; }
.markdown-body th { background: var(--bg-tertiary); font-weight: 600; }
.markdown-body hr { border: none; border-top: 1px solid var(--border); margin: 1em 0; }

/* Code block wrapper */
.code-block-wrapper { position: relative; margin: 0.75em 0; border-radius: 10px; overflow: hidden; border: 1px solid var(--border); background: var(--bg-tertiary); }
.code-block-wrapper pre { margin: 0; padding: 1em; overflow-x: auto; font-size: 0.82em; line-height: 1.6; }
.code-block-wrapper pre code { font-family: 'JetBrains Mono', 'Fira Code', monospace; background: none; border: none; padding: 0; color: var(--text-primary); }
.code-lang-label { position: absolute; top: 0; right: 0; font-size: 0.6rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 0.2em 0.6em; color: var(--text-muted); background: var(--bg-secondary); border-bottom-left-radius: 6px; border-left: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.code-copy-btn { position: absolute; top: 0.35em; right: 4em; font-size: 0.65rem; font-weight: 600; padding: 0.2em 0.6em; border-radius: 5px; border: 1px solid var(--border); background: var(--bg-secondary); color: var(--text-muted); cursor: pointer; transition: all 0.15s; opacity: 0; }
.code-block-wrapper:hover .code-copy-btn { opacity: 1; }
.code-copy-btn:hover { color: var(--accent); border-color: var(--accent); }

/* Stop generation button */
.stop-btn { flex-shrink: 0; background: rgba(239, 68, 68, 0.15); border: none; color: #ef4444; padding: 0.55rem; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.stop-btn:hover { background: rgba(239, 68, 68, 0.25); }

/* Input actions row */
.input-actions { display: flex; align-items: center; justify-content: space-between; max-width: 900px; margin: 0 auto; }
.input-actions .action-btn { width: auto; height: auto; border-radius: 6px; background: none; border: none; color: var(--text-muted); font-size: 0.7rem; font-weight: 500; padding: 0.3rem 0.5rem; cursor: pointer; display: flex; align-items: center; gap: 0.3rem; transition: all 0.15s; }
.input-actions .action-btn:hover { color: var(--accent); background: var(--accent-glow); }
.input-actions .action-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.input-actions .input-hint { flex: 1; }

/* Sidebar history header */
.history-header { display: flex; align-items: center; justify-content: space-between; padding: 0 0.25rem; }
.history-header .section-label { margin-bottom: 0; }
.history-actions { display: flex; gap: 0.25rem; }
.sidebar-icon-btn { background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 0.3rem; border-radius: 5px; display: flex; transition: all 0.15s; }
.sidebar-icon-btn:hover { color: var(--accent); background: var(--accent-glow); }
.sidebar-icon-btn:disabled { opacity: 0.3; cursor: not-allowed; }

/* Search input */
.history-search { padding: 0.25rem 0 0.5rem; }
.search-input { width: 100%; padding: 0.45rem 0.65rem; font-size: 0.78rem; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-tertiary); color: var(--text-primary); outline: none; transition: border-color 0.2s; }
.search-input::placeholder { color: var(--text-muted); }
.search-input:focus { border-color: var(--accent); }

/* Error message bubble */
.msg-bubble.error .msg-content { border-color: rgba(239, 68, 68, 0.3); background: rgba(239, 68, 68, 0.05); }

@media (max-width: 480px) {
  .chat-header { padding: 0.5rem 0.6rem; }
  .header-mode { font-size: 0.75rem; }
  .msg-avatar { width: 26px; height: 26px; border-radius: 6px; }
  .msg-content { font-size: 0.84rem; padding: 0.6rem 0.75rem; }
  .msg-bubble { max-width: 92%; border-radius: 12px; }
  .quick-prompts { flex-direction: column; gap: 0.4rem; }
  .quick-btn { width: 100%; font-size: 0.78rem; padding: 0.55rem 0.75rem; }
  .empty-title { font-size: 1rem; }
  .empty-subtitle { font-size: 0.8rem; }
  .input-container { border-radius: 12px; padding: 0.3rem 0.4rem; }
  .chat-input { font-size: 0.85rem; padding: 0.5rem 0.4rem; }
  .mic-btn { width: 44px; height: 44px; }
  .voice-transcript { padding: 0.5rem 0.75rem; }
  .transcript-text { font-size: 0.85rem; }
  .search-input { font-size: 0.75rem; padding: 0.4rem 0.6rem; }
  .code-block-wrapper pre { padding: 0.5em; font-size: 0.72em; }
  .code-copy-btn { opacity: 1; font-size: 0.6rem; }
  .voice-overlay-content { padding: 1.5rem; }
  .voice-visualizer { width: 180px; height: 180px; }
  .orb-outer { width: 110px; height: 110px; }
  .orb-inner { width: 80px; height: 80px; }
  .orb-inner svg { width: 30px; height: 30px; }
  .voice-title { font-size: 1.15rem; }
  .transcript-line { font-size: 0.95rem; }
  .transcript-line.pending { font-size: 1.1rem; }
  .action-btn { width: 48px; height: 48px; }
  .voice-metrics { gap: 0.35rem; }
  .metric-chip { font-size: 0.65rem; padding: 0.2rem 0.6rem; }
}

@supports (padding-bottom: env(safe-area-inset-bottom)) {
  .input-area { padding-bottom: calc(0.75rem + env(safe-area-inset-bottom)); }
}
</style>
