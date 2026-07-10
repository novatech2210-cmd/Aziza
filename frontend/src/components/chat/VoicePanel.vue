<script setup>
import { ref, onUnmounted } from 'vue'

const props = defineProps({
  mode: { type: String, default: 'voice-text' },
  language: { type: String, default: 'en' },
})

const emit = defineEmits(['transcription'])

const CHAT_API = import.meta.env.VITE_CHAT_API_URL || '/chat-api'

const isRecording = ref(false)
const status = ref('idle') // idle | recording | transcribing | speaking
const audioLevel = ref(0)
const canvasRef = ref(null)
let mediaRecorder = null
let audioChunks = []
let analyser = null
let animationId = null
let audioStream = null

async function startRecording() {
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(audioStream)
    audioChunks = []

    // Set up analyser for waveform
    const audioCtx = new AudioContext()
    const source = audioCtx.createMediaStreamSource(audioStream)
    analyser = audioCtx.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)

    mediaRecorder.ondataavailable = (e) => {
      audioChunks.push(e.data)
    }

    mediaRecorder.onstop = async () => {
      cancelAnimationFrame(animationId)
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
      await transcribe(audioBlob)
    }

    mediaRecorder.start()
    isRecording.value = true
    status.value = 'recording'
    drawWaveform()
  } catch (err) {
    status.value = 'idle'
    alert('Microphone access denied')
  }
}

function stopRecording() {
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.stop()
  }
  if (audioStream) {
    audioStream.getTracks().forEach((t) => t.stop())
    audioStream = null
  }
  isRecording.value = false
  status.value = 'transcribing'
}

async function transcribe(audioBlob) {
  try {
    const formData = new FormData()
    formData.append('file', audioBlob, 'recording.webm')
    formData.append('language', props.language)

    const token = localStorage.getItem('aziza_token')
    const response = await fetch(`${CHAT_API}/transcribe`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    })

    if (!response.ok) throw new Error('Transcription failed')
    const data = await response.json()
    emit('transcription', data.text || data.transcription || '')
    status.value = 'idle'
  } catch (err) {
    console.error('Transcription error:', err)
    status.value = 'idle'
  }
}

function drawWaveform() {
  if (!analyser || !canvasRef.value) return
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  const bufferLength = analyser.frequencyBinCount
  const dataArray = new Uint8Array(bufferLength)

  function draw() {
    animationId = requestAnimationFrame(draw)
    analyser.getByteTimeDomainData(dataArray)

    ctx.fillStyle = '#1a1a1a'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    ctx.lineWidth = 2
    ctx.strokeStyle = '#14b8a6'
    ctx.beginPath()

    const sliceWidth = canvas.width / bufferLength
    let x = 0
    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0
      const y = (v * canvas.height) / 2
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
      x += sliceWidth
    }
    ctx.lineTo(canvas.width, canvas.height / 2)
    ctx.stroke()

    // Calculate audio level
    let sum = 0
    for (let i = 0; i < bufferLength; i++) {
      const v = (dataArray[i] - 128) / 128
      sum += v * v
    }
    audioLevel.value = Math.sqrt(sum / bufferLength)
  }

  draw()
}

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  if (audioStream) audioStream.getTracks().forEach((t) => t.stop())
})
</script>

<template>
  <div class="bg-[#252525] rounded-xl p-3 flex items-center gap-3">
    <!-- Record Button -->
    <button
      @click="isRecording ? stopRecording() : startRecording()"
      :class="[
        'w-12 h-12 rounded-full flex items-center justify-center transition shrink-0',
        isRecording
          ? 'bg-red-500 hover:bg-red-600 animate-pulse'
          : 'bg-teal-600 hover:bg-teal-700'
      ]"
    >
      <svg v-if="!isRecording" class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
      </svg>
      <svg v-else class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
        <rect x="6" y="6" width="12" height="12" rx="2" />
      </svg>
    </button>

    <!-- Waveform -->
    <canvas ref="canvasRef" width="200" height="40" class="flex-1 rounded-lg" />

    <!-- Status -->
    <span class="text-xs text-gray-400 shrink-0 min-w-[90px] text-right">
      <span v-if="status === 'idle'">Tap to record</span>
      <span v-else-if="status === 'recording'" class="text-red-400">● Recording</span>
      <span v-else-if="status === 'transcribing'" class="text-yellow-400">Transcribing...</span>
      <span v-else-if="status === 'speaking'" class="text-teal-400">Speaking...</span>
    </span>
  </div>
</template>
