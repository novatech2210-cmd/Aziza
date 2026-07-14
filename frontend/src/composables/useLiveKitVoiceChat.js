/**
 * AZIZA — LiveKit Voice Chat Composable (PI-4)
 *
 * Integrates LiveKit as the real-time audio transport layer while preserving
 * the existing AZIZA WebSocket control plane.
 *
 * Architecture:
 *   Microphone → LiveKit Audio Track → AZIZA Gateway (LiveKit Bot) → Moshi Worker
 *   Moshi Worker → LiveKit Bot → LiveKit Audio Track → Speaker
 */

import { ref, onUnmounted } from 'vue'
import { generateUUID } from '../utils/uuid.js'
import { Room, Track, createLocalAudioTrack } from 'livekit-client'

const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || 'ws://localhost:7880'
const LIVEKIT_API_KEY = import.meta.env.VITE_LIVEKIT_API_KEY || 'devkey'
const LIVEKIT_API_SECRET = import.meta.env.VITE_LIVEKIT_API_SECRET || 'devsecret'

export function useLiveKitVoiceChat() {
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const muted = ref(false)
  const amplitude = ref(0)
  const transcript = ref('')
  const completedSentences = ref([])
  const pendingSentence = ref('')
  const errorMessage = ref('')
  const sessionId = ref('')
  const assistantState = ref('IDLE')
  const latencyP50 = ref(0)
  const latencyP95 = ref(0)
  const activeDeviceId = ref('')
  const availableDevices = ref([])
  const liveKitConnected = ref(false)

  const e2eMetrics = ref({
    timeToFirstChunk: 0,
    voiceToVoiceLatency: 0,
    voiceToTextLatency: 0,
    liveKitLatency: 0,
    packetLoss: 0,
    jitter: 0,
  })

  let room = null
  let localAudioTrack = null
  let remoteAudioTrack = null
  let audioContext = null
  let analyserNode = null
  let gainNode = null
  let lastUserSpeechStart = 0
  let isUserSpeaking = false
  let responseTracked = true
  let moshiSpeaking = false
  let playbackCheckTimer = null
  let reconnectTimer = null
  let reconnectAttempt = 0
  let shouldReconnect = false
  let animationFrameId = null

  // ---- Device Management ----

  async function loadDevices() {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      availableDevices.value = devices.filter(d => d.kind === 'audioinput')
    } catch (err) {
      console.error('[LiveKit] Failed to enumerate devices:', err)
    }
  }

  async function switchDevice(deviceId) {
    if (!isConnected.value) return
    activeDeviceId.value = deviceId
    await disconnect()
    await connect(deviceId)
  }

  // ---- LiveKit Connection ----

  async function connect(deviceId, language = 'ru') {
    if (isConnected.value || isConnecting.value) return
    reconnectAttempt = 0
    isConnecting.value = true
    errorMessage.value = ''
    completedSentences.value = []
    pendingSentence.value = ''
    transcript.value = ''
    if (deviceId) activeDeviceId.value = deviceId

    try {
      const sid = generateUUID() || Math.random().toString(36).slice(2)
      sessionId.value = sid

      const token = await generateLiveKitToken(sid)
      await loadDevices()

      room = new Room()

      room.on('connected', () => {
        console.log('[LiveKit] Connected to room')
        liveKitConnected.value = true
        isConnecting.value = false
        shouldReconnect = true
        reconnectAttempt = 0
      })

      room.on('disconnected', () => {
        console.log('[LiveKit] Disconnected from room')
        liveKitConnected.value = false
        isConnected.value = false
        if (shouldReconnect) scheduleReconnect()
      })

      room.on('trackSubscribed', (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          console.log('[LiveKit] Subscribed to remote audio from', participant.identity)
          remoteAudioTrack = track
          setupRemoteAudioPlayback(track)
        }
      })

      room.on('reconnecting', () => {
        console.log('[LiveKit] Reconnecting...')
        errorMessage.value = 'Reconnecting to voice service...'
      })

      room.on('reconnected', () => {
        console.log('[LiveKit] Reconnected')
        errorMessage.value = ''
        reconnectAttempt = 0
      })

      room.on('localTrackPublished', () => {
        console.log('[LiveKit] Local track published')
      })

      await room.connect(LIVEKIT_URL, token)

      // Create and publish local audio track
      const audioTrack = await createLocalAudioTrack({
        deviceId: deviceId || undefined,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 48000,
        channelCount: 1,
      })

      localAudioTrack = audioTrack
      await room.localParticipant.publishTrack(audioTrack)
      
      isConnected.value = true
      shouldReconnect = true

      // Establish WebSocket control connection
      await connectControlWebSocket(sid, language)

    } catch (err) {
      errorMessage.value = err.message || 'Failed to connect to LiveKit'
      isConnecting.value = false
      if (shouldReconnect) scheduleReconnect()
    }
  }

  async function connectControlWebSocket(sid, language) {
    // Placeholder: integrate with existing WebSocket control plane
    console.log(`[LiveKit] Control WebSocket for session ${sid}, language ${language}`)
  }

  function disconnect() {
    shouldReconnect = false
    cancelReconnect()

    if (room) {
      room.disconnect()
      room = null
    }

    if (audioContext) {
      audioContext.close().catch(() => {})
      audioContext = null
    }

    isConnected.value = false
    isConnecting.value = false
    liveKitConnected.value = false
    assistantState.value = 'IDLE'
    localAudioTrack = null
    remoteAudioTrack = null
  }

  // ---- Audio Playback ----

  function setupRemoteAudioPlayback(track) {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)()
    }

    const mediaStream = new MediaStream([track])
    const source = audioContext.createMediaStreamSource(mediaStream)

    analyserNode = audioContext.createAnalyser()
    analyserNode.fftSize = 256

    gainNode = audioContext.createGain()
    source.connect(analyserNode)
    analyserNode.connect(gainNode)
    gainNode.connect(audioContext.destination)

    gainNode.gain.setTargetAtTime(0.2, audioContext.currentTime, 0.1)
    moshiSpeaking = true
    if (assistantState.value === 'IDLE') assistantState.value = 'SPEAKING'

    if (playbackCheckTimer) clearTimeout(playbackCheckTimer)
    playbackCheckTimer = setTimeout(() => {
      moshiSpeaking = false
      assistantState.value = 'IDLE'
      playbackCheckTimer = null
      if (gainNode) gainNode.gain.setTargetAtTime(1.0, audioContext.currentTime, 0.1)
    }, 1000)

    monitorAmplitude()
  }

  function monitorAmplitude() {
    if (!analyserNode) return
    const dataArray = new Uint8Array(analyserNode.frequencyBinCount)

    function update() {
      if (!isConnected.value) return
      analyserNode.getByteTimeDomainData(dataArray)
      let sum = 0
      for (let i = 0; i < dataArray.length; i++) {
        const v = (dataArray[i] - 128) / 128
        sum += v * v
      }
      amplitude.value = Math.sqrt(sum / dataArray.length)
      animationFrameId = requestAnimationFrame(update)
    }
    update()
  }

  // ---- Reconnection ----

  function scheduleReconnect() {
    if (!shouldReconnect || reconnectTimer) return
    if (reconnectAttempt >= 15) {
      errorMessage.value = 'Connection lost — tap to reconnect'
      isConnecting.value = false
      return
    }
    const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempt), 30000)
    const jitter = delay * (0.75 + Math.random() * 0.5)
    reconnectAttempt++
    console.log(`[LiveKit] Reconnecting in ${Math.round(jitter)}ms (attempt ${reconnectAttempt})`)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect(activeDeviceId.value)
    }, jitter)
  }

  function cancelReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    reconnectAttempt = 0
  }

  // ---- Token Generation ----

  async function generateLiveKitToken(roomName, participantName = 'user') {
    const CHAT_API = import.meta.env.VITE_CHAT_API_URL || '/api'
    const token = localStorage.getItem('aziza_token') || ''

    const response = await fetch(`${CHAT_API}/livekit/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ roomName, participantName }),
    })

    if (!response.ok) {
      throw new Error('Failed to generate LiveKit token')
    }

    const data = await response.json()
    return data.token
  }

  // ---- Controls ----

  function toggleMute() {
    muted.value = !muted.value
    if (room && room.localParticipant) {
      room.localParticipant.setMicrophoneEnabled(!muted.value)
    }
    if (muted.value) amplitude.value = 0
  }

  function updateLanguage(lang) {
    console.log(`[LiveKit] Language update: ${lang}`)
  }

  onUnmounted(() => {
    shouldReconnect = false
    cancelReconnect()
    disconnect()
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId)
    }
  })

  return {
    isConnected,
    isConnecting,
    liveKitConnected,
    muted,
    amplitude,
    transcript,
    completedSentences,
    pendingSentence,
    errorMessage,
    sessionId,
    assistantState,
    latencyP50,
    latencyP95,
    e2eMetrics,
    activeDeviceId,
    availableDevices,
    connect,
    disconnect,
    toggleMute,
    updateLanguage,
    loadDevices,
    switchDevice,
  }
}
