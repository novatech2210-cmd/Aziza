<script setup>
import { ref, onUnmounted } from 'vue'
import { useVoiceChat } from '../../composables/useVoiceChat.js'
import { useLiveKitVoiceChat } from '../../composables/useLiveKitVoiceChat.js'

const props = defineProps({
  mode: { type: String, default: 'voice-text' },
  language: { type: String, default: 'en' },
  transport: { type: String, default: 'websocket' }, // 'websocket' | 'livekit'
})

const emit = defineEmits(['transcription'])

const isRecording = ref(false)
const status = ref('idle')
const audioLevel = ref(0)
const canvasRef = ref(null)
let mediaRecorder = null
let audioChunks = []
let analyser = null
let animationId = null
let audioStream = null

// Use appropriate voice chat composable based on transport
const voiceChat = props.transport === 'livekit' 
  ? useLiveKitVoiceChat() 
  : useVoiceChat()

async function startRecording() {
  try {
    await voiceChat.connect(undefined, props.language)
    isRecording.value = true
    status.value = 'recording'
  } catch (err) {
    status.value = 'idle'
    alert('Microphone access denied: ' + err.message)
  }
}

function stopRecording() {
  voiceChat.disconnect()
  isRecording.value = false
  status.value = 'idle'
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
