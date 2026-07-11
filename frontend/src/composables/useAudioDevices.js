import { ref, onMounted, onUnmounted } from 'vue'

const STORAGE_KEY = 'aziza_preferred_mic'

export function useAudioDevices() {
  const devices = ref([])
  const selectedDeviceId = ref(localStorage.getItem(STORAGE_KEY) || '')
  const permissionState = ref('prompt') // prompt | granted | denied | unknown
  const isEnumerating = ref(false)

  let _stream = null

  async function enumerateDevices() {
    isEnumerating.value = true
    try {
      const all = await navigator.mediaDevices.enumerateDevices()
      devices.value = all.filter(d => d.kind === 'audioinput')

      // If no device selected and we have devices, pick default
      if (!selectedDeviceId.value && devices.value.length > 0) {
        const defaultDevice = devices.value.find(d => d.deviceId === 'default')
        if (defaultDevice) {
          selectedDeviceId.value = defaultDevice.deviceId
        }
      }

      // Update permission state based on label availability
      if (devices.value.length > 0 && devices.value[0].label) {
        permissionState.value = 'granted'
      }
    } catch (err) {
      console.warn('[Aziza] enumerateDevices failed:', err.name)
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        permissionState.value = 'denied'
      }
    } finally {
      isEnumerating.value = false
    }
  }

  async function requestPermission() {
    try {
      // Request mic access with a temporary stream to trigger permission prompt
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      permissionState.value = 'granted'

      // Stop the temporary stream immediately
      _stream.getTracks().forEach(t => t.stop())
      _stream = null

      // Now enumerate with labels available
      await enumerateDevices()
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        permissionState.value = 'denied'
      } else {
        permissionState.value = 'unknown'
      }
    }
  }

  function selectDevice(deviceId) {
    selectedDeviceId.value = deviceId
    localStorage.setItem(STORAGE_KEY, deviceId)
  }

  function handleDeviceChange() {
    // Re-enumerate when devices change (hot-swap)
    const prevSelected = selectedDeviceId.value
    enumerateDevices().then(() => {
      // If selected device disappeared, fall back to default
      if (prevSelected && !devices.value.find(d => d.deviceId === prevSelected)) {
        const defaultDevice = devices.value.find(d => d.deviceId === 'default')
        if (defaultDevice) {
          selectDevice(defaultDevice.deviceId)
        } else if (devices.value.length > 0) {
          selectDevice(devices.value[0].deviceId)
        }
      }
    })
  }

  onMounted(() => {
    enumerateDevices()
    if (navigator.mediaDevices) {
      navigator.mediaDevices.addEventListener('devicechange', handleDeviceChange)
    }
  })

  onUnmounted(() => {
    if (_stream) {
      _stream.getTracks().forEach(t => t.stop())
      _stream = null
    }
    if (navigator.mediaDevices) {
      navigator.mediaDevices.removeEventListener('devicechange', handleDeviceChange)
    }
  })

  return {
    devices,
    selectedDeviceId,
    permissionState,
    isEnumerating,
    enumerateDevices,
    requestPermission,
    selectDevice,
  }
}
