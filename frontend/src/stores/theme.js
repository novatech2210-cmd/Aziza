import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: localStorage.getItem('aziza_theme') || 'dark',
  }),

  getters: {
    isDark: (state) => state.mode === 'dark',
  },

  actions: {
    toggle() {
      this.mode = this.mode === 'dark' ? 'light' : 'dark'
      localStorage.setItem('aziza_theme', this.mode)
      this.apply()
    },

    apply() {
      document.documentElement.setAttribute('data-theme', this.mode)
    },

    init() {
      this.apply()
    },
  },
})
