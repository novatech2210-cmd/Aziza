import { generateUUID } from '../utils/uuid.js'
/**
 * AZIZA — Full-duplex voice chat composable (Phase 7.1)
 *
 * Handles:
 *   - WebSocket connection to /ws/voice/{session_id}
 *   - Opus recording via opus-recorder (24kHz mono)
 *   - Opus decoding via ogg-opus-decoder (WASM)
 *   - Web Audio API playback with scheduled buffering
 *   - Barge-in interruption (user speaks over AI)
 *   - Gain ducking (0.2x) while AI is speaking
 *   - Reconnect with exponential backoff (1s→30s, jitter)
 *   - FSM state tracking (IDLE / SPEAKING / INTERRUPTIBLE)
 *   - New control messages: assistant_state, latency, keepalive, barge_in
 *
 * Fixes:
 *   - Removed forced 24kHz AudioContext to fix "demon sound" pitch issues.
 *   - Enhanced echo suppression with 1s trailing window.
 */

import { ref, onUnmounted } from 'vue'

const CHAT_WS_BASE = import.meta.env.VITE_CHAT_WS_URL || ((location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host)
const TAG_AUDIO = 0x01
const TAG_TEXT  = 0x02
const TAG_CTRL  = 0x03

// Reconnect backoff settings
const BACKOFF_INITIAL_MS = 1000
const BACKOFF_MAX_MS = 30000
const BACKOFF_MULTIPLIER = 1.5
const BACKOFF_MAX_ATTEMPTS = 15

export function useVoiceChat() {
  const isConnected     = ref(false)
  const isConnecting    = ref(false)
  const muted           = ref(false)
  const amplitude       = ref(0)
  const transcript      = ref('')
  const completedSentences = ref([])
  const pendingSentence = ref('')
  const errorMessage    = ref('')
  const sessionId       = ref('')
  const assistantState  = ref('IDLE')          // FSM: IDLE | LISTENING | SPEAKING | INTERRUPTIBLE | PROCESSING
  const latencyP50      = ref(0)               // Server-reported p50 latency (ms)
  const latencyP95      = ref(0)               // Server-reported p95 latency (ms)
  const activeDeviceId  = ref('')              // Currently used audio input device

  // End-to-end frontend metrics
  const e2eMetrics = ref({
    timeToFirstChunk: 0,
    voiceToVoiceLatency: 0,
    voiceToTextLatency: 0
  })

  let lastUserSpeechStart = 0
  let isUserSpeaking = false
  let responseTracked = true // True means we are waiting for user to speak again

  let ws = null
  let recorder = null
  let micStream = null
  let audioContext = null
  let decoderRef = null
  let analyserCtx = null
  let analyserNode = null
  let animFrameId = null
  let moshiSpeaking = false
  let playbackCheckTimer = null
  let gainNode = null                           // For volume ducking
  let playbackNode = null
  let voiceCaptureNode = null

  // Reconnect state
  let reconnectTimer = null
  let reconnectAttempt = 0
  let shouldReconnect = false                   // True after first successful connect

  // ---- Decoder placeholder (no longer used) ----

  async function initDecoder() {
    console.log('[Aziza] Raw PCM mode ready (No Opus decoder needed)')
  }

  // ---- Audio Playback ----

  async function initAudioContext() {
    if (audioContext) return
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    console.log(`[Aziza] AudioContext initialized at ${audioContext.sampleRate}Hz`)
    
    // Load the custom playback processor
    await audioContext.audioWorklet.addModule('/worklets/playback-processor.js')
    playbackNode = new AudioWorkletNode(audioContext, 'playback-processor', {
      processorOptions: {
        bufferSize: 96000,
        minJitterFrames: 2400
      }
    })

    // Create a gain node for volume ducking
    gainNode = audioContext.createGain()
    playbackNode.connect(gainNode)
    gainNode.connect(audioContext.destination)

    playbackNode.port.onmessage = (e) => {
      if (e.data.type === 'underrun') {
        console.warn('[Aziza] Audio playback underrun')
      }
    }
  }

  function scheduleAudioPlayback(float32Pcm) {
    if (!audioContext || !playbackNode || !float32Pcm || float32Pcm.length === 0) return

    playbackNode.port.postMessage({ type: 'audio', data: float32Pcm })

    // Update speaking flag for echo suppression
    if (!moshiSpeaking) {
      moshiSpeaking = true
      if (assistantState.value === 'IDLE') assistantState.value = 'SPEAKING'
    }

    // Monitor playback completion (reset after 1s of silence)
    if (playbackCheckTimer) clearTimeout(playbackCheckTimer)
    playbackCheckTimer = setTimeout(() => {
      moshiSpeaking = false
      assistantState.value = 'IDLE'
      playbackCheckTimer = null
      // Restore gain after AI stops speaking
      if (gainNode) gainNode.gain.setTargetAtTime(1.0, audioContext.currentTime, 0.1)
    }, 1000)
  }

  /** Stop all pending Moshi audio (user barge-in). */
  function interruptPlayback() {
    if (playbackNode) {
      playbackNode.port.postMessage({ type: 'interrupt' })
    }
    moshiSpeaking = false
    assistantState.value = 'IDLE'
    if (playbackCheckTimer) { clearTimeout(playbackCheckTimer); playbackCheckTimer = null }
    // Restore gain immediately
    if (gainNode && audioContext) {
      gainNode.gain.setValueAtTime(1.0, audioContext.currentTime)
    }
    console.log('[Aziza] Playback interrupted (barge-in)')
  }

  // ---- PCM Recording ----

  async function startRecording(deviceId) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error(
        window.isSecureContext
          ? 'Microphone access is not available in this browser.'
          : 'Microphone requires HTTPS. Use the Cloudflare tunnel URL or access via localhost.'
      )
    }
    const audioConstraints = {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1
    }
    if (deviceId) {
      audioConstraints.deviceId = { exact: deviceId }
    }
    micStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints })

    analyserCtx = new (window.AudioContext || window.webkitAudioContext)()
    const micSourceNode = analyserCtx.createMediaStreamSource(micStream)

    analyserNode = analyserCtx.createAnalyser()
    analyserNode.fftSize = 256
    micSourceNode.connect(analyserNode)

    await analyserCtx.audioWorklet.addModule('/worklets/voice-capture-processor.js')
    voiceCaptureNode = new AudioWorkletNode(analyserCtx, 'voice-capture-processor', {
      processorOptions: {
        targetSampleRate: 24000,
        bufferSize: 1920 // 80ms chunk
      }
    })

    voiceCaptureNode.port.onmessage = (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN || muted.value) return
      
      if (e.data.type === 'audio') {
        const int16 = e.data.data; // Int16Array
        
        // Calculate audio level for visualization
        let sum = 0
        for (let j = 0; j < int16.length; j++) {
          const s = int16[j] / 32768.0
          sum += s * s
        }
        amplitude.value = Math.sqrt(sum / int16.length)

        if (moshiSpeaking && amplitude.value < 0.25) {
          return
        }
        
        // Track user speaking start for latency measurements
        if (amplitude.value > 0.15 && !isUserSpeaking) {
          isUserSpeaking = true
          lastUserSpeechStart = Date.now()
          responseTracked = false
        } else if (amplitude.value <= 0.15) {
          isUserSpeaking = false
        }

        // Barge-in check
        if (moshiSpeaking && amplitude.value > 0.3) {
          interruptPlayback()
        }

        // Prepend 0x01 (TAG_AUDIO)
        const packet = new Uint8Array(1 + int16.byteLength)
        packet[0] = 0x01
        packet.set(new Uint8Array(int16.buffer), 1)

        ws.send(packet.buffer)
      }
    }

    micSourceNode.connect(voiceCaptureNode)
    voiceCaptureNode.connect(analyserCtx.destination)
    recorder = { stop: () => voiceCaptureNode.disconnect() }

    console.log('[Aziza] PCM recording started (24kHz)')
  }

  function stopRecording() {
    if (animFrameId) {
      cancelAnimationFrame(animFrameId)
      animFrameId = null
    }
    if (playbackCheckTimer) {
      clearTimeout(playbackCheckTimer)
      playbackCheckTimer = null
    }
    moshiSpeaking = false
    if (recorder) {
      try { recorder.stop() } catch {}
      recorder = null
    }
    if (analyserCtx) {
      try { analyserCtx.close() } catch {}
      analyserCtx = null
      analyserNode = null
    }
    if (micStream) {
      micStream.getTracks().forEach(t => t.stop())
      micStream = null
    }
    amplitude.value = 0
  }

  // ---- Reconnect with exponential backoff ----

  function scheduleReconnect() {
    if (!shouldReconnect || reconnectTimer) return
    if (reconnectAttempt >= BACKOFF_MAX_ATTEMPTS) {
      errorMessage.value = 'Connection lost — tap to reconnect'
      isConnecting.value = false
      isConnected.value = false
      return
    }
    const delay = Math.min(
      BACKOFF_INITIAL_MS * Math.pow(BACKOFF_MULTIPLIER, reconnectAttempt),
      BACKOFF_MAX_MS
    )
    const jitter = delay * (0.75 + Math.random() * 0.5)
    reconnectAttempt++
    console.log(`[Aziza] Reconnecting in ${Math.round(jitter)}ms (attempt ${reconnectAttempt})`)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, jitter)
  }

  function cancelReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    reconnectAttempt = 0
  }

  // ---- Control Message Handlers ----

  function handleControlMessage(data) {
    switch (data.type) {
      case 'assistant_state':
        assistantState.value = data.state || 'IDLE'
        // Apply gain ducking when AI is speaking
        if (gainNode && audioContext) {
          if (data.state === 'SPEAKING' || data.state === 'INTERRUPTIBLE') {
            gainNode.gain.setTargetAtTime(0.2, audioContext.currentTime, 0.1)
            // Immediately flag as speaking to suppress echo before playback starts
            moshiSpeaking = true 
          } else {
            // We'll let the playbackCheckTimer reset IDLE state to account for audio tail
          }
        }
        break

      case 'latency':
        latencyP50.value = data.p50_ms || 0
        latencyP95.value = data.p95_ms || 0
        break

      case 'keepalive':
        break

      case 'barge_in':
        interruptPlayback()
        break

      case 'vad_state':
        // Server-side VAD state update
        if (data.state === 'speaking') {
          assistantState.value = 'LISTENING'
        } else if (data.state === 'idle' && data.is_speech === false) {
          // End of turn - user stopped speaking
          assistantState.value = 'PROCESSING'
        }
        break

      case 'partial_transcript':
        if (data.text) {
          pendingSentence.value = data.text
        }
        break

      case 'final_transcript':
        if (data.text) {
          completedSentences.value.push(data.text)
          pendingSentence.value = ''
        }
        break

      default:
        break
    }
  }

  // ---- WebSocket ----

  async function connect(deviceId) {
    if (isConnected.value || isConnecting.value) return
    reconnectAttempt = 0
    isConnecting.value = true
    errorMessage.value = ''
    completedSentences.value = []
    pendingSentence.value = ''
    transcript.value = ''
    if (deviceId) activeDeviceId.value = deviceId

    try {
      await initAudioContext()

      if (decoderRef) {
        try { await decoderRef.reset() } catch {
          try { decoderRef.free() } catch {}
          decoderRef = null
        }
      }
      if (!decoderRef) {
        await initDecoder()
      }

      if (audioContext.state === 'suspended') {
        await audioContext.resume()
      }

      const sid = generateUUID() || Math.random().toString(36).slice(2)
      sessionId.value = sid
      const token = localStorage.getItem('aziza_token') || ''
      const url = `${CHAT_WS_BASE}/api/chat?sessionId=${sid}&token=${token}`

      const connectTo = (socketUrl) => {
        ws = new WebSocket(socketUrl)

        ws.onopen = () => {}

        ws.onmessage = async (event) => {
          if (typeof event.data === 'string') {
            try {
              const data = JSON.parse(event.data)
              if (data.type === 'error') {
                errorMessage.value = data.message || 'Unknown error'
                isConnecting.value = false
              } else if (data.type === 'ping') {
                try {
                  ws.send(JSON.stringify({ type: 'pong' }))
                } catch {}
              } else if (data.type === 'worker_assigned') {
                console.log('[Aziza] Worker assigned, redirecting to', data.ws_url)
                ws.onclose = null // Prevent teardown
                ws.close()
                connectTo(data.ws_url)
              } else {
                handleControlMessage(data)
              }
            } catch {}
            return
          }

          const arrayBuffer = await event.data.arrayBuffer()
          const view = new Uint8Array(arrayBuffer)
          if (view.length < 1) return
          const tag = view[0]
          const payload = arrayBuffer.slice(1)

          if (tag === 0x00) {
            // Handshake received
            isConnecting.value = false
            shouldReconnect = true
            reconnectAttempt = 0
            cancelReconnect()
            try {
              await startRecording(activeDeviceId.value || undefined)
              isConnected.value = true
            } catch (recErr) {
              errorMessage.value = recErr.message || 'Failed to start microphone'
              ws?.close()
            }
            return
          }

          if (tag === TAG_AUDIO) {
            try {
              if (!responseTracked && lastUserSpeechStart > 0) {
                const now = Date.now()
                const latency = now - lastUserSpeechStart
                e2eMetrics.value.timeToFirstChunk = latency
                e2eMetrics.value.voiceToVoiceLatency = latency
                responseTracked = true
                console.log(`[Aziza] Voice↔Voice Latency: ${latency}ms`)
              }

              // Backend Moshi sends Float32Array bytes
              const float32Array = new Float32Array(payload.buffer, payload.byteOffset, payload.byteLength / 4)
              if (float32Array.length > 0) {
                scheduleAudioPlayback(float32Array)
              }
            } catch (e) {
              console.error('Audio decode error', e)
            }
          }

          if (tag === TAG_TEXT) {
            const text = new TextDecoder().decode(payload)
            pendingSentence.value += text
            transcript.value += text

            if (!responseTracked && lastUserSpeechStart > 0) {
              const now = Date.now()
              const latency = now - lastUserSpeechStart
              e2eMetrics.value.voiceToTextLatency = latency
              console.log(`[Aziza] Voice→Text Latency: ${latency}ms`)
              // We don't set responseTracked to true here because we still want to track Voice->Voice
            }

            if (/[.!?]$/.test(pendingSentence.value)) {
              completedSentences.value.push(pendingSentence.value)
              pendingSentence.value = ''
            }
          }

          if (tag === TAG_CTRL) {
            try {
              const ctrl = JSON.parse(new TextDecoder().decode(payload))
              handleControlMessage(ctrl)
            } catch {}
          }
        }

        ws.onclose = (ev) => {
          const wasConnected = isConnected.value
          isConnected.value = false
          isConnecting.value = false
          stopRecording()
          assistantState.value = 'IDLE'

          if (wasConnected && shouldReconnect && ev.code !== 1000) {
            scheduleReconnect()
          }
        }

        ws.onerror = () => {
          errorMessage.value = 'WebSocket connection failed'
          isConnecting.value = false
          ws?.close()
        }
      }

      connectTo(url)
    } catch (err) {
      errorMessage.value = err.message || 'Failed to start voice chat'
      isConnecting.value = false
      if (shouldReconnect) {
        scheduleReconnect()
      }
    }
  }

  function disconnect() {
    shouldReconnect = false
    cancelReconnect()
    stopRecording()
    if (ws) {
      try { ws.close(1000) } catch {}
      ws = null
    }
    isConnected.value = false
    isConnecting.value = false
    assistantState.value = 'IDLE'
    latencyP50.value = 0
    latencyP95.value = 0
  }

  function toggleMute() {
    muted.value = !muted.value
    if (muted.value) amplitude.value = 0
  }

  function clearTranscript() {
    transcript.value = ''
    completedSentences.value = []
    pendingSentence.value = ''
  }

  function updateLanguage(lang) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        const payload = JSON.stringify({ type: 'session_update', language: lang })
        const textBytes = new TextEncoder().encode(payload)
        const buffer = new Uint8Array(1 + textBytes.length)
        buffer[0] = TAG_CTRL
        buffer.set(textBytes, 1)
        ws.send(buffer)
      } catch (err) {
        console.error('Failed to send session_update', err)
      }
    }
  }

  onUnmounted(() => {
    shouldReconnect = false
    cancelReconnect()
    disconnect()
    if (decoderRef) {
      try { decoderRef.free() } catch {}
      decoderRef = null
    }
    if (audioContext) {
      try { audioContext.close() } catch {}
      audioContext = null
    }
  })

  return {
    isConnected,
    isConnecting,
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
    connect,
    disconnect,
    updateLanguage,
    toggleMute,
    clearTranscript,
  }
}
