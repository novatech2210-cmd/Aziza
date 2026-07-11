import { generateUUID } from '../utils/uuid.js'
import { defineStore } from 'pinia'
import { useAuthStore } from './auth'

const CHAT_WS_BASE = import.meta.env.VITE_CHAT_WS_URL || `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`
const AUTH_API_BASE = import.meta.env.VITE_AUTH_API_URL || '/api/auth'
const CHAT_API_BASE = import.meta.env.VITE_CHAT_API_URL || '/api'

// Reconnect config
const RECONNECT_BASE_DELAY = 500
const RECONNECT_MAX_DELAY = 5000
const RECONNECT_MAX_ATTEMPTS = 20

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    sessionId: generateUUID(),
    connectionState: 'disconnected', // 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
    reconnectAttempt: 0,
    isStreaming: false,
    selectedLanguage: 'auto',
    detectedLanguage: null, // { language, detected, is_mixed, layout_corrected, confidence }
    selectedMode: 'text',
    wsConnection: null,
    sessionHistory: JSON.parse(localStorage.getItem('aziza_session_history') || '[]'),
    _reconnectTimer: null,
    _pingTimer: null,
    _userId: null,
    _intentionalClose: false,
  }),

  getters: {
    isConnected: (state) => state.connectionState === 'connected',
  },

  actions: {
    connect(userId) {
      if (this.wsConnection?.readyState === WebSocket.OPEN) return
      this._userId = userId
      this._intentionalClose = false
      this.connectionState = this.reconnectAttempt > 0 ? 'reconnecting' : 'connecting'

      const token = localStorage.getItem('aziza_token')
      const url = `${CHAT_WS_BASE}/api/chat-text?sessionId=${this.sessionId}`

      try {
        const ws = new WebSocket(url, ["token", token])

        ws.onopen = () => {
          this.connectionState = 'connected'
          this.reconnectAttempt = 0
          // Client-side keepalive ping every 20s
          if (this._pingTimer) clearInterval(this._pingTimer)
          this._pingTimer = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }))
            }
          }, 20000)
        }

        ws.onmessage = (event) => {
          const data = JSON.parse(event.data)
          this._handleIncoming(data)
        }

        ws.onclose = (e) => {
          this.wsConnection = null
          if (e.code === 1008 || e.code === 4401) {
            const auth = useAuthStore()
            auth.logout()
            return
          }
          if (!this._intentionalClose) {
            // Stay "connected" visually for first 2 attempts (silent reconnect)
            if (this.reconnectAttempt >= 2) {
              this.connectionState = 'reconnecting'
            }
            this._scheduleReconnect()
          } else {
            this.connectionState = 'disconnected'
          }
        }

        ws.onerror = () => {
          ws.close()
        }

        this.wsConnection = ws
      } catch {
        this.connectionState = 'reconnecting'
        this._scheduleReconnect()
      }
    },

    _scheduleReconnect() {
      if (this.reconnectAttempt >= RECONNECT_MAX_ATTEMPTS) {
        this.connectionState = 'disconnected'
        this.reconnectAttempt = 0
        return
      }
      if (this._reconnectTimer) clearTimeout(this._reconnectTimer)
      const delay = Math.min(
        RECONNECT_BASE_DELAY * Math.pow(1.5, this.reconnectAttempt),
        RECONNECT_MAX_DELAY
      )
      const jitter = delay * (0.75 + Math.random() * 0.5)
      this.reconnectAttempt++
      this._reconnectTimer = setTimeout(() => {
        this.connect(this._userId)
      }, jitter)
    },

    sendMessage(text) {
      if (!this.wsConnection || this.wsConnection.readyState !== WebSocket.OPEN) return

      const userMsg = {
        id: generateUUID(),
        role: 'user',
        content: text,
        timestamp: new Date().toISOString(),
        isStreaming: false,
      }
      this.messages.push(userMsg)

      this.wsConnection.send(JSON.stringify({
        message: text,
        language: this.selectedLanguage,
        mode: this.selectedMode,
      }))

      this.messages.push({
        id: generateUUID(),
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        isStreaming: true,
      })
      this.isStreaming = true
    },

    _handleIncoming(data) {
      // Language detection result
      if (data.type === 'lang_detected') {
        this.detectedLanguage = data
        if (data.layout_corrected) {
          window.dispatchEvent(new CustomEvent('aziza-toast', {
            detail: {
              type: 'info',
              message: `Keyboard layout corrected (${data.language.toUpperCase()})`,
              duration: 3000,
            },
          }))
        }
        return
      }

      // Respond to server heartbeat ping
      if (data.type === 'ping') {
        if (this.wsConnection?.readyState === WebSocket.OPEN) {
          this.wsConnection.send(JSON.stringify({ type: 'pong' }))
        }
        return
      }

      const lastMsg = this.messages[this.messages.length - 1]

      if (data.type === 'token' && lastMsg?.role === 'assistant') {
        lastMsg.content += data.content
      } else if (data.type === 'done') {
        if (lastMsg?.role === 'assistant') {
          lastMsg.isStreaming = false
        }
        this.isStreaming = false
        this._persistHistory()
      } else if (data.type === 'error') {
        const isLimitError = data.message?.includes('limit reached')
        if (isLimitError) {
          // Remove the empty assistant placeholder and the user message
          if (lastMsg?.role === 'assistant' && !lastMsg.content) {
            this.messages.pop()
          }
          if (this.messages.length && this.messages[this.messages.length - 1]?.role === 'user') {
            this.messages.pop()
          }
          window.dispatchEvent(new CustomEvent('aziza-toast', {
            detail: { type: 'warning', message: data.message, duration: 8000 },
          }))
        } else {
          if (lastMsg?.role === 'assistant') {
            lastMsg.content = `Error: ${data.message}`
            lastMsg.isStreaming = false
            lastMsg.isError = true
          }
          window.dispatchEvent(new CustomEvent('aziza-toast', {
            detail: { type: 'error', message: data.message || 'Something went wrong' },
          }))
        }
        this.isStreaming = false
      }
    },

    disconnect() {
      this._intentionalClose = true
      if (this._reconnectTimer) {
        clearTimeout(this._reconnectTimer)
        this._reconnectTimer = null
      }
      if (this._pingTimer) {
        clearInterval(this._pingTimer)
        this._pingTimer = null
      }
      if (this.wsConnection) {
        this.wsConnection.close()
        this.wsConnection = null
      }
      this.connectionState = 'disconnected'
    },

    newSession() {
      if (this.messages.length > 0) {
        const existing = this.sessionHistory.find(s => s.id === this.sessionId)
        if (existing) {
          // Update existing entry
          existing.messages = [...this.messages]
          existing.preview = this.messages[0]?.content?.slice(0, 50) || 'New Chat'
          existing.timestamp = new Date().toISOString()
          existing.language = this.selectedLanguage
          existing.mode = this.selectedMode
          existing.messageCount = this.messages.length
        } else {
          this.sessionHistory.unshift({
            id: this.sessionId,
            messages: [...this.messages],
            timestamp: new Date().toISOString(),
            preview: this.messages[0]?.content?.slice(0, 50) || 'New Chat',
            language: this.selectedLanguage,
            mode: this.selectedMode,
            messageCount: this.messages.length,
          })
        }
        // Limit history to 50 sessions
        if (this.sessionHistory.length > 50) this.sessionHistory.pop()
        this._saveHistoryLocal()
      }
      this.messages = []
      this.sessionId = generateUUID()
      this.isStreaming = false
    },

    loadSession(session) {
      // Save current if has messages
      if (this.messages.length > 0 && this.sessionId !== session.id) {
        const existing = this.sessionHistory.find(s => s.id === this.sessionId)
        if (!existing) {
          this.sessionHistory.unshift({
            id: this.sessionId,
            messages: [...this.messages],
            timestamp: new Date().toISOString(),
            preview: this.messages[0]?.content?.slice(0, 50) || 'New Chat',
            language: this.selectedLanguage,
            mode: this.selectedMode,
            messageCount: this.messages.length,
          })
        }
      }
      this.sessionId = session.id
      this.messages = [...session.messages]
    },

    async deleteSession(sessionId) {
      this.sessionHistory = this.sessionHistory.filter(s => s.id !== sessionId)
      this._saveHistoryLocal()
      // If deleting the current session, start a new one
      if (this.sessionId === sessionId) {
        this.messages = []
        this.sessionId = generateUUID()
        this.isStreaming = false
      }
      // Delete from server DB — await to ensure it completes before any reload
      const token = localStorage.getItem('aziza_token')
      if (token) {
        try {
          await fetch(`${AUTH_API_BASE}/chat-history/${sessionId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` },
          })
        } catch {}
      }
    },

    _persistHistory() {
      this._saveHistoryLocal()
      this._saveHistoryRemote()
    },

    _saveHistoryLocal() {
      try {
        localStorage.setItem('aziza_session_history', JSON.stringify(this.sessionHistory))
      } catch {}
    },

    async _saveHistoryRemote() {
      const token = localStorage.getItem('aziza_token')
      if (!token || this.messages.length === 0) return
      try {
        await fetch(`${AUTH_API_BASE}/chat-history`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            session_id: this.sessionId,
            messages: this.messages,
            language: this.selectedLanguage,
            mode: this.selectedMode,
            preview: this.messages[0]?.content?.slice(0, 100) || 'Chat',
          }),
        })
      } catch {}
    },

    async loadHistoryFromServer() {
      const token = localStorage.getItem('aziza_token')
      if (!token) return
      try {
        const res = await fetch(`${AUTH_API_BASE}/chat-history`, {
          headers: { 'Authorization': `Bearer ${token}` },
        })
        if (res.ok) {
          const remote = await res.json()
          // Server is source of truth — deduplicate by session ID
          const seen = new Set()
          const merged = []
          // Server sessions take priority
          for (const s of remote) {
            if (!seen.has(s.id)) {
              seen.add(s.id)
              merged.push(s)
            }
          }
          // Keep local-only sessions (unsaved current session)
          for (const s of this.sessionHistory) {
            if (!seen.has(s.id)) {
              seen.add(s.id)
              merged.push(s)
            }
          }
          this.sessionHistory = merged.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
          this._saveHistoryLocal()
        }
      } catch {}
    },

    setLanguage(lang) {
      this.selectedLanguage = lang
      if (this.wsConnection?.readyState === 1) { // WebSocket.OPEN
        this.wsConnection.send(JSON.stringify({ type: 'session_update', language: lang }))
      }
    },

    setMode(mode) {
      this.selectedMode = mode
    },

    stopGeneration() {
      if (!this.isStreaming) return
      // Mark the streaming message as done
      const lastMsg = this.messages[this.messages.length - 1]
      if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
        lastMsg.isStreaming = false
      }
      this.isStreaming = false
      // Send stop signal to server
      if (this.wsConnection?.readyState === WebSocket.OPEN) {
        this.wsConnection.send(JSON.stringify({ type: 'stop' }))
      }
    },

    retryLastMessage() {
      if (this.isStreaming) return
      // Find the last user message
      let lastUserIdx = -1
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === 'user') {
          lastUserIdx = i
          break
        }
      }
      if (lastUserIdx === -1) return
      // Remove everything after the last user message
      this.messages.splice(lastUserIdx + 1)
      // Re-send the user message
      const text = this.messages[lastUserIdx].content
      // Remove the user message too (sendMessage will re-add it)
      this.messages.splice(lastUserIdx, 1)
      this.sendMessage(text)
    },
  },
})
