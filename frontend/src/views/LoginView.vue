<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

const auth = useAuthStore()
const router = useRouter()
const theme = useThemeStore()

const isRegister = ref(false)
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const mounted = ref(false)

onMounted(() => {
  setTimeout(() => { mounted.value = true }, 50)
})

async function handleSubmit() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = 'Please fill in all fields'
    return
  }
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(username.value, password.value)
    } else {
      await auth.login(username.value, password.value)
    }
    router.push(auth.isAdmin ? '/admin' : '/chat')
  } catch (e) {
    console.error('Login error:', e)
    if (e.response?.data?.detail) {
      error.value = e.response.data.detail
    } else if (e.request) {
      error.value = 'Network error - is the server accessible?'
    } else {
      error.value = e.message || 'Something went wrong'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- Animated background orbs -->
    <div class="bg-orbs">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
      <div class="orb orb-4"></div>
    </div>

    <!-- Grid pattern overlay -->
    <div class="grid-overlay"></div>

    <!-- Floating particles -->
    <div class="particles">
      <div v-for="i in 20" :key="i" class="particle" :style="{
        left: Math.random() * 100 + '%',
        top: Math.random() * 100 + '%',
        animationDelay: Math.random() * 6 + 's',
        animationDuration: (4 + Math.random() * 6) + 's',
        width: (2 + Math.random() * 4) + 'px',
        height: (2 + Math.random() * 4) + 'px',
      }"></div>
    </div>

    <!-- Theme toggle -->
    <button class="theme-toggle" @click="theme.toggle()" :title="theme.isDark ? 'Switch to light mode' : 'Switch to dark mode'">
      <svg v-if="theme.isDark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
      <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
    </button>

    <div class="login-container" :class="{ 'visible': mounted }">
      <!-- Logo -->
      <div class="logo-section">
        <div class="logo-icon-wrap">
          <div class="logo-ring"></div>
          <div class="logo-icon">
            <svg width="52" height="52" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="14" fill="url(#logo-grad)" />
              <path d="M14 32L24 14L34 32H14Z" fill="white" opacity="0.95" />
              <defs>
                <linearGradient id="logo-grad" x1="0" y1="0" x2="48" y2="48">
                  <stop stop-color="#14b8a6" />
                  <stop offset="0.5" stop-color="#06b6d4" />
                  <stop offset="1" stop-color="#8b5cf6" />
                </linearGradient>
              </defs>
            </svg>
          </div>
        </div>
        <h1 class="logo-text">
          <span class="letter" v-for="(l, i) in 'AZIZA'" :key="i" :style="{ animationDelay: (0.1 * i) + 's' }">{{ l }}</span>
        </h1>
        <p class="logo-subtitle">
          <span class="subtitle-line"></span>
          AI Assistant Platform
          <span class="subtitle-line"></span>
        </p>
      </div>

      <!-- Card with animated border -->
      <div class="card-border-wrap">
        <div class="card-border-glow"></div>
        <div class="login-card">
          <h2 class="card-title">
            {{ isRegister ? 'Create Account' : 'Welcome Back' }}
          </h2>
          <p class="card-desc">
            {{ isRegister ? 'Sign up to get started with AZIZA' : 'Sign in to continue your conversation' }}
          </p>

          <!-- Error -->
          <Transition name="shake">
            <div v-if="error" class="error-box">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {{ error }}
            </div>
          </Transition>

          <form @submit.prevent="handleSubmit" class="login-form">
            <div class="form-group anim-field" style="animation-delay: 0.3s">
              <label class="form-label">Username</label>
              <div class="input-wrapper">
                <svg class="input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <input
                  v-model="username"
                  type="text"
                  class="form-input"
                  placeholder="Enter username"
                  autocomplete="username"
                />
                <div class="input-glow"></div>
              </div>
            </div>

            <div class="form-group anim-field" style="animation-delay: 0.45s">
              <label class="form-label">Password</label>
              <div class="input-wrapper">
                <svg class="input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <input
                  v-model="password"
                  type="password"
                  class="form-input"
                  placeholder="Enter password"
                  autocomplete="current-password"
                />
                <div class="input-glow"></div>
              </div>
            </div>

            <button type="submit" :disabled="loading" class="submit-btn anim-field" style="animation-delay: 0.6s">
              <div class="btn-shine"></div>
              <svg v-if="loading" class="spinner" viewBox="0 0 24 24">
                <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                <path class="spinner-fill" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <template v-else>
                {{ isRegister ? 'Create Account' : 'Sign In' }}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </template>
            </button>
          </form>

          <div class="divider anim-field" style="animation-delay: 0.7s">
            <span>or</span>
          </div>

          <div class="toggle-section anim-field" style="animation-delay: 0.8s">
            {{ isRegister ? 'Already have an account?' : "Don't have an account?" }}
            <button
              @click="isRegister = !isRegister; error = ''"
              class="toggle-btn"
            >
              {{ isRegister ? 'Sign In' : 'Create Account' }}
            </button>
          </div>
        </div>
      </div>

      <p class="footer-text anim-field" style="animation-delay: 0.9s">
        <span class="footer-dot"></span>
        Powered by AZIZA AI
        <span class="footer-dot"></span>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
  padding: 1rem;
  position: relative;
  overflow: hidden;
}

/* ===== Animated Background Orbs ===== */
.bg-orbs {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: var(--glow-opacity);
}

.orb-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, #14b8a6 0%, transparent 70%);
  top: -15%;
  right: -10%;
  animation: orbFloat1 12s ease-in-out infinite;
}

.orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, #8b5cf6 0%, transparent 70%);
  bottom: -15%;
  left: -10%;
  animation: orbFloat2 15s ease-in-out infinite;
}

.orb-3 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, #06b6d4 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: orbFloat3 10s ease-in-out infinite;
}

.orb-4 {
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, #ec4899 0%, transparent 70%);
  top: 20%;
  left: 15%;
  animation: orbFloat4 18s ease-in-out infinite;
  opacity: calc(var(--glow-opacity) * 0.5);
}

@keyframes orbFloat1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-60px, 40px) scale(1.1); }
  66% { transform: translate(30px, -20px) scale(0.9); }
}

@keyframes orbFloat2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(50px, -50px) scale(1.15); }
  66% { transform: translate(-30px, 30px) scale(0.85); }
}

@keyframes orbFloat3 {
  0%, 100% { transform: translate(-50%, -50%) scale(1); }
  50% { transform: translate(-50%, -50%) scale(1.3); }
}

@keyframes orbFloat4 {
  0%, 100% { transform: translate(0, 0); }
  25% { transform: translate(80px, 20px); }
  50% { transform: translate(40px, -60px); }
  75% { transform: translate(-40px, -20px); }
}

/* ===== Grid Pattern ===== */
.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--border) 1px, transparent 1px),
    linear-gradient(90deg, var(--border) 1px, transparent 1px);
  background-size: 60px 60px;
  opacity: 0.15;
  pointer-events: none;
  mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black, transparent);
  -webkit-mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black, transparent);
}

/* ===== Floating Particles ===== */
.particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.particle {
  position: absolute;
  background: var(--accent);
  border-radius: 50%;
  opacity: 0;
  animation: particleFloat linear infinite;
}

@keyframes particleFloat {
  0% { opacity: 0; transform: translateY(0) scale(0); }
  10% { opacity: 0.6; transform: translateY(-20px) scale(1); }
  90% { opacity: 0.3; transform: translateY(-120px) scale(0.5); }
  100% { opacity: 0; transform: translateY(-150px) scale(0); }
}

/* ===== Theme Toggle ===== */
.theme-toggle {
  position: absolute;
  top: 1.25rem;
  right: 1.25rem;
  z-index: 10;
  background: var(--bg-glass);
  border: 1px solid var(--bg-glass-border);
  color: var(--text-secondary);
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  backdrop-filter: blur(12px);
}

.theme-toggle:hover {
  color: var(--accent);
  border-color: var(--accent);
  box-shadow: 0 0 20px var(--accent-glow);
  transform: rotate(15deg);
}

/* ===== Container + Entrance Animation ===== */
.login-container {
  width: 100%;
  max-width: 460px;
  position: relative;
  z-index: 1;
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.login-container.visible {
  opacity: 1;
  transform: translateY(0);
}

/* ===== Logo Section ===== */
.logo-section {
  text-align: center;
  margin-bottom: 2.5rem;
}

.logo-icon-wrap {
  position: relative;
  display: inline-block;
  margin-bottom: 1.25rem;
}

.logo-ring {
  position: absolute;
  inset: -10px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: var(--accent);
  border-right-color: rgba(139, 92, 246, 0.5);
  animation: ringRotate 3s linear infinite;
}

@keyframes ringRotate {
  to { transform: rotate(360deg); }
}

.logo-icon {
  position: relative;
  filter: drop-shadow(0 0 25px rgba(20, 184, 166, 0.5));
  animation: logoPulse 3s ease-in-out infinite;
}

@keyframes logoPulse {
  0%, 100% { filter: drop-shadow(0 0 25px rgba(20, 184, 166, 0.5)); }
  50% { filter: drop-shadow(0 0 40px rgba(20, 184, 166, 0.7)); }
}

.logo-text {
  font-size: 3rem;
  font-weight: 800;
  letter-spacing: 0.2em;
  display: flex;
  justify-content: center;
  gap: 2px;
}

.letter {
  display: inline-block;
  background: linear-gradient(135deg, #14b8a6, #06b6d4, #8b5cf6, #14b8a6);
  background-size: 300% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: letterWave 3s ease infinite, shimmer 4s ease infinite;
}

@keyframes letterWave {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

@keyframes shimmer {
  0% { background-position: 0% center; }
  100% { background-position: 300% center; }
}

.logo-subtitle {
  color: var(--text-secondary);
  font-size: 0.85rem;
  margin-top: 0.5rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
}

.subtitle-line {
  display: inline-block;
  width: 30px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
}

/* ===== Card with Animated Border ===== */
.card-border-wrap {
  position: relative;
  border-radius: 22px;
  padding: 1px;
}

.card-border-glow {
  position: absolute;
  inset: -1px;
  border-radius: 22px;
  background: conic-gradient(
    from 0deg,
    #14b8a6, #06b6d4, #8b5cf6, #ec4899,
    #14b8a6, #06b6d4, #8b5cf6, #ec4899,
    #14b8a6
  );
  animation: borderRotate 6s linear infinite;
  opacity: 0.4;
  filter: blur(1px);
}

@keyframes borderRotate {
  to { transform: rotate(360deg); }
}

.card-border-glow::after {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 21px;
  background: var(--bg-primary);
}

.login-card {
  position: relative;
  z-index: 1;
  background: var(--bg-glass);
  backdrop-filter: blur(24px);
  border: 1px solid var(--bg-glass-border);
  border-radius: 22px;
  padding: 2.75rem 2.25rem 2.25rem;
  box-shadow:
    0 25px 70px var(--shadow),
    0 0 0 1px var(--bg-glass-inset) inset;
}

.card-title {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-primary);
  text-align: center;
  margin-bottom: 0.35rem;
}

.card-desc {
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-align: center;
  margin-bottom: 2rem;
}

/* ===== Error ===== */
.error-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--danger-bg);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: var(--danger);
  padding: 0.75rem 1rem;
  border-radius: 12px;
  font-size: 0.85rem;
  margin-bottom: 1.25rem;
  animation: shakeIn 0.4s ease;
}

@keyframes shakeIn {
  0% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
  100% { transform: translateX(0); }
}

.shake-enter-active { animation: shakeIn 0.4s ease; }
.shake-leave-active { transition: opacity 0.2s; }
.shake-leave-to { opacity: 0; }

/* ===== Form ===== */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.anim-field {
  opacity: 0;
  transform: translateY(12px);
  animation: fieldAppear 0.5s ease forwards;
}

@keyframes fieldAppear {
  to { opacity: 1; transform: translateY(0); }
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.input-wrapper {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
  transition: all 0.3s;
}

.input-wrapper:focus-within .input-icon {
  color: var(--accent);
  filter: drop-shadow(0 0 6px var(--accent-glow));
}

.form-input {
  width: 100%;
  background: var(--bg-input);
  border: 1.5px solid var(--border);
  border-radius: 14px;
  padding: 0.9rem 1rem 0.9rem 2.75rem;
  font-size: 0.95rem;
  color: var(--text-primary);
  outline: none;
  transition: all 0.3s;
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow), 0 0 20px var(--accent-glow);
  background: var(--bg-primary);
}

.input-glow {
  position: absolute;
  inset: 0;
  border-radius: 14px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s;
  box-shadow: 0 0 30px var(--accent-glow);
}

.input-wrapper:focus-within .input-glow {
  opacity: 1;
}

/* ===== Submit Button ===== */
.submit-btn {
  width: 100%;
  background: linear-gradient(135deg, #14b8a6, #0891b2, #8b5cf6);
  background-size: 200% auto;
  color: white;
  font-weight: 600;
  font-size: 1rem;
  padding: 0.95rem;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.3s;
  margin-top: 0.5rem;
  box-shadow: 0 4px 20px rgba(20, 184, 166, 0.3);
  position: relative;
  overflow: hidden;
  animation-name: fieldAppear, btnGradient;
  animation-duration: 0.5s, 3s;
  animation-timing-function: ease, ease;
  animation-fill-mode: forwards, none;
  animation-iteration-count: 1, infinite;
}

@keyframes btnGradient {
  0% { background-position: 0% center; }
  50% { background-position: 100% center; }
  100% { background-position: 0% center; }
}

.btn-shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.15),
    transparent
  );
  animation: btnShine 3s ease-in-out infinite;
}

@keyframes btnShine {
  0%, 100% { left: -100%; }
  50% { left: 100%; }
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(20, 184, 166, 0.4), 0 0 40px rgba(139, 92, 246, 0.15);
}

.submit-btn:active {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* ===== Spinner ===== */
.spinner {
  width: 1.25rem;
  height: 1.25rem;
  animation: spin 1s linear infinite;
}

.spinner-track { opacity: 0.25; }
.spinner-fill { opacity: 0.75; }

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== Divider ===== */
.divider {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 1.75rem 0;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border), transparent);
}

.divider span {
  font-size: 0.7rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.15em;
}

/* ===== Toggle ===== */
.toggle-section {
  text-align: center;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.toggle-btn {
  background: none;
  border: none;
  color: var(--accent);
  font-weight: 600;
  cursor: pointer;
  margin-left: 0.25rem;
  font-size: 0.875rem;
  transition: all 0.2s;
  position: relative;
}

.toggle-btn::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 0;
  height: 1.5px;
  background: var(--accent);
  transition: width 0.3s;
}

.toggle-btn:hover {
  color: #2dd4bf;
  text-shadow: 0 0 12px var(--accent-glow);
}

.toggle-btn:hover::after {
  width: 100%;
}

/* ===== Footer ===== */
.footer-text {
  text-align: center;
  margin-top: 2.25rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
}

.footer-dot {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0.5;
  animation: dotPulse 2s ease-in-out infinite;
}

@keyframes dotPulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 0.8; transform: scale(1.2); }
}

/* ===== Responsive ===== */
@media (max-width: 480px) {
  .login-card {
    padding: 2rem 1.5rem 1.75rem;
  }

  .logo-text {
    font-size: 2.5rem;
  }
}
</style>
