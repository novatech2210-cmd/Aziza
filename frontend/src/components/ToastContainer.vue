<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const toasts = ref([])
let idCounter = 0

function addToast(event) {
  const { type, message, duration } = event.detail
  const id = ++idCounter
  toasts.value.push({ id, type: type || 'info', message, fading: false })
  setTimeout(() => removeToast(id), duration || 5000)
}

function removeToast(id) {
  const t = toasts.value.find(t => t.id === id)
  if (t) {
    t.fading = true
    setTimeout(() => {
      toasts.value = toasts.value.filter(t => t.id !== id)
    }, 300)
  }
}

onMounted(() => {
  window.addEventListener('aziza-toast', addToast)
})
onUnmounted(() => {
  window.removeEventListener('aziza-toast', addToast)
})

function icon(type) {
  if (type === 'error') return 'M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4m0 4h.01'
  if (type === 'success') return 'M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3'
  if (type === 'warning') return 'M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4m0 4h.01'
  return 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zm0-14v4m0 4h.01'
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :class="['toast', toast.type, { fading: toast.fading }]"
        @click="removeToast(toast.id)"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path :d="icon(toast.type)" />
        </svg>
        <span class="toast-msg">{{ toast.message }}</span>
        <button class="toast-close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
  max-width: 400px;
}

.toast {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  border: 1px solid;
  backdrop-filter: blur(12px);
  font-size: 0.82rem;
  cursor: pointer;
  pointer-events: auto;
  animation: slideIn 0.3s ease-out;
  transition: opacity 0.3s, transform 0.3s;
}

.toast.fading {
  opacity: 0;
  transform: translateX(20px);
}

.toast.error {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.25);
  color: #f87171;
}

.toast.success {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.25);
  color: #4ade80;
}

.toast.warning {
  background: rgba(234, 179, 8, 0.12);
  border-color: rgba(234, 179, 8, 0.25);
  color: #facc15;
}

.toast.info {
  background: rgba(59, 130, 246, 0.12);
  border-color: rgba(59, 130, 246, 0.25);
  color: #60a5fa;
}

.toast-msg {
  flex: 1;
  line-height: 1.4;
}

.toast-close {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  padding: 2px;
  display: flex;
  flex-shrink: 0;
}

.toast-close:hover {
  opacity: 1;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(40px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
