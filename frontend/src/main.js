import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// Global Vue error handler — prevents silent component crashes
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err, info)
  window.dispatchEvent(new CustomEvent('aziza-toast', {
    detail: { type: 'error', message: 'Something went wrong. Please refresh the page.' },
  }))
}

// Catch unhandled async rejections outside Vue components
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Rejection]', event.reason)
  event.preventDefault()
})

app.mount('#app')

// Initialize theme from localStorage
import { useThemeStore } from './stores/theme'
useThemeStore().init()
