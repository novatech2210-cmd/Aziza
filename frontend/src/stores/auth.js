import { defineStore } from 'pinia'
import axios from 'axios'
import router from '../router'

// Base URL for auth API — configurable for production (VPS tunnel URL)
const API_BASE = import.meta.env.VITE_AUTH_API_URL || '/api/auth'

// Axios instance for auth requests
const authApi = axios.create({ baseURL: API_BASE })

// Attach token to all axios requests globally
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('aziza_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401, try refresh; on refresh failure, logout
let _refreshing = false

axios.interceptors.response.use(
  (res) => res,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry && !_refreshing) {
      originalRequest._retry = true
      _refreshing = true
      try {
        const { data } = await authApi.post('/refresh')
        localStorage.setItem('aziza_token', data.access_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        return axios(originalRequest)
      } catch {
        const auth = useAuthStore()
        auth.logout()
      } finally {
        _refreshing = false
      }
    }
    return Promise.reject(error)
  }
)

/**
 * Fetch wrapper that auto-handles 401 → refresh → retry → logout.
 * Use this instead of raw fetch() for authenticated requests.
 */
export async function authFetch(url, options = {}) {
  const token = localStorage.getItem('aziza_token')
  const headers = { ...options.headers }
  if (token) headers.Authorization = `Bearer ${token}`

  let res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    if (!_refreshing) {
      _refreshing = true
      try {
        const refreshRes = await authApi.post('/refresh')
        localStorage.setItem('aziza_token', refreshRes.data.access_token)
        headers.Authorization = `Bearer ${refreshRes.data.access_token}`
        res = await fetch(url, { ...options, headers })
      } catch {
        const auth = useAuthStore()
        auth.logout()
        return res
      } finally {
        _refreshing = false
      }
    } else {
      const auth = useAuthStore()
      auth.logout()
    }
  }

  return res
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('aziza_user') || 'null'),
    token: localStorage.getItem('aziza_token') || '',
    refreshToken: localStorage.getItem('aziza_refresh_token') || '',
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin',
  },

  actions: {
    _saveAuth(data) {
      this.token = data.access_token
      this.refreshToken = data.refresh_token || 'mock-refresh-token'
      this.user = data.user || { role: 'admin', email: 'test@example.com' }
      localStorage.setItem('aziza_token', this.token)
      localStorage.setItem('aziza_refresh_token', this.refreshToken)
      localStorage.setItem('aziza_user', JSON.stringify(this.user))
    },

    async login(email, password) {
      if (import.meta.env.VITE_DEV_SKIP_AUTH === 'true') {
        this._saveAuth({ access_token: 'mock-token', user: { email, role: 'admin' } })
        return
      }
      const { data } = await authApi.post('/login', { email, password })
      this._saveAuth(data)
    },

    async register(email, password) {
      if (import.meta.env.VITE_DEV_SKIP_AUTH === 'true') {
        this._saveAuth({ access_token: 'mock-token', user: { email, role: 'admin' } })
        return
      }
      const { data } = await authApi.post('/register', { email, password })
      this._saveAuth(data)
    },

    logout() {
      this.token = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem('aziza_token')
      localStorage.removeItem('aziza_refresh_token')
      localStorage.removeItem('aziza_user')
      router.push('/login')
    },

    async fetchMe() {
      if (import.meta.env.VITE_DEV_SKIP_AUTH === 'true') {
        this.user = { email: 'test@example.com', role: 'admin' }
        return
      }
      try {
        const { data } = await authApi.get('/me', {
          headers: { Authorization: `Bearer ${this.token}` },
        })
        this.user = data
        localStorage.setItem('aziza_user', JSON.stringify(data))
      } catch {
        this.logout()
      }
    },
  },
})
