import { defineStore } from 'pinia'
import http from '../utils/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('urban-flow-token') || '',
    user: JSON.parse(localStorage.getItem('urban-flow-user') || 'null'),
  }),
  getters: {
    permissions: (state) => state.user?.permissions || [],
    isAdmin: (state) => state.user?.roles?.some((role) => (role.code || role) === 'admin') || false,
  },
  actions: {
    async login(credentials) {
      const result = await http.post('/auth/login', credentials)
      this.token = result.access_token
      this.user = result.user
      localStorage.setItem('urban-flow-token', this.token)
      localStorage.setItem('urban-flow-user', JSON.stringify(this.user))
    },
    async refresh() {
      if (!this.token) return
      this.user = await http.get('/auth/me')
      localStorage.setItem('urban-flow-user', JSON.stringify(this.user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('urban-flow-token')
      localStorage.removeItem('urban-flow-user')
    },
    can(permission) {
      return this.permissions.includes(permission)
    },
  },
})
