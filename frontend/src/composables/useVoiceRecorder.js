/**
 * Voice Recorder composable for streaming ASR.
 *
 * Captures microphone audio, resamples to 16kHz PCM int16,
 * streams chunks via WebSocket to the ASR backend,
 * and receives partial/final transcripts.
 *
 * Usage:
 *   const { isRecording, partialText, finalText, start, stop, state } = useVoiceRecorder()
 */

import { ref, onUnmounted } from 'vue'

export function useVoiceRecorder() {
  const isRecording = ref(false)
  const state = ref('idle') // idle | requesting | recording | processing | done | error
  const partialText = ref('')
  const finalText = ref('')
  const errorMessage = ref('')
  const audioLevel = ref(0) 

  let recognition = null;
  let audioContext = null;
  let mediaStream = null;
  let analyserNode = null;
  let animFrameId = null;

  function initRecognition(language) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      throw new Error('Speech Recognition API not supported in this browser. Please use Chrome.')
    }
    recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    
    // Map 'auto', 'en', 'ru' to standard locales
    if (language === 'ru') {
      recognition.lang = 'ru-RU'
    } else if (language === 'en') {
      recognition.lang = 'en-US'
    } else {
      // Let browser auto-detect or default
      recognition.lang = 'en-US'
    }

    recognition.onstart = () => {
      isRecording.value = true
      state.value = 'recording'
    }

    recognition.onresult = (event) => {
      let interimTranscript = ''
      let finalTranscript = ''

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript
        } else {
          interimTranscript += event.results[i][0].transcript
        }
      }
      
      partialText.value = interimTranscript
      if (finalTranscript) {
        finalText.value += (finalText.value ? ' ' : '') + finalTranscript
      }
    }

    recognition.onerror = (event) => {
      errorMessage.value = `Speech recognition error: ${event.error}`
      state.value = 'error'
      stop()
    }

    recognition.onend = () => {
      if (isRecording.value) {
        stop()
      }
    }
  }

  async function start(language, deviceId) {
    if (isRecording.value) return
    state.value = 'requesting'
    errorMessage.value = ''
    partialText.value = ''
    finalText.value = ''

    try {
      const constraints = { audio: true }
      if (deviceId) {
        constraints.audio = { deviceId: { exact: deviceId } }
      }
      mediaStream = await navigator.mediaDevices.getUserMedia(constraints)
      audioContext = new (window.AudioContext || window.webkitAudioContext)()
      const source = audioContext.createMediaStreamSource(mediaStream)
      analyserNode = audioContext.createAnalyser()
      analyserNode.fftSize = 256
      source.connect(analyserNode)
      
      function processAmplitude() {
        if (!isRecording.value) return
        const dataArray = new Uint8Array(analyserNode.frequencyBinCount)
        analyserNode.getByteFrequencyData(dataArray)
        let sum = 0;
        for(let i=0; i<dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length
        audioLevel.value = (avg / 255)
        animFrameId = requestAnimationFrame(processAmplitude)
      }
      processAmplitude()

      initRecognition(language)
      recognition.start()
    } catch (err) {
      errorMessage.value = err.message || 'Failed to start recording'
      state.value = 'error'
      _cleanup()
    }
  }

  function stop() {
    if (!isRecording.value) return
    isRecording.value = false
    state.value = 'processing'

    if (recognition) {
      recognition.stop()
    }
    
    // Convert partial to final if any
    if (partialText.value) {
      finalText.value += (finalText.value ? ' ' : '') + partialText.value
      partialText.value = ''
    }

    _cleanup()
    state.value = 'done'
  }

  function reset() {
    state.value = 'idle'
    partialText.value = ''
    finalText.value = ''
    errorMessage.value = ''
    audioLevel.value = 0
  }

  function _cleanup() {
    if (animFrameId) cancelAnimationFrame(animFrameId)
    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.stop())
      mediaStream = null
    }
    if (audioContext) {
      audioContext.close().catch(() => {})
      audioContext = null
    }
    isRecording.value = false
    audioLevel.value = 0
  }

  onUnmounted(() => {
    if (recognition) {
      try { recognition.stop() } catch {}
    }
    _cleanup()
  })

  return {
    isRecording,
    state,
    partialText,
    finalText,
    errorMessage,
    audioLevel,
    start,
    stop,
    reset
  }
}
