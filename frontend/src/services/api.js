import axios from 'axios'

const api = axios.create({ baseURL: '' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const USER_UPDATED = 'user-updated'

export const authService = {
  register: (data) => api.post('/api/auth/register', data),

  login: async (email, password) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    return api.post('/api/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },

  getMe: () => api.get('/api/auth/me'),
  updateMe: (data) => api.patch('/api/users/me', data),
  deleteMyAccount: () => api.delete('/api/users/me'),

  changePassword: (currentPassword, newPassword) =>
    api.post('/api/auth/password', {
      current_password: currentPassword, new_password: newPassword,
    }),
  forgotPassword: (email) => api.post('/api/auth/password/forgot', { email }),
  submitSecurityAnswers: (email, answers, message) =>
    api.post('/api/auth/password/answers', { email, answers, message }),
  appealForReset: (email, message) =>
    api.post('/api/auth/password/appeal', { email, message }),
  resetStatus: (claim) =>
    api.get('/api/auth/password/status', { params: { claim } }),
  resetPassword: (claim, newPassword) =>
    api.post('/api/auth/password/reset', { claim, new_password: newPassword }),

  securityQuestions: () => api.get('/api/auth/security-questions'),
  setSecurityQuestions: (pairs) =>
    api.put('/api/auth/security-questions', { pairs }),
  logout: () => { localStorage.removeItem('token'); localStorage.removeItem('user') },

  getCachedUser: () => JSON.parse(localStorage.getItem('user') || '{}'),

  setCachedUser: (user) => {
    localStorage.setItem('user', JSON.stringify(user))
    window.dispatchEvent(new Event(USER_UPDATED))
  },
}

export const profileService = {
  get: () => api.get('/api/profiles/me'),
  create: (data) => api.post('/api/profiles/me', data),
  update: (data) => api.put('/api/profiles/me', data),

  listPublications: () => api.get('/api/profiles/me/publications'),
  addPublication: (data) => api.post('/api/profiles/me/publications', data),
  updatePublication: (id, data) => api.put(`/api/profiles/me/publications/${id}`, data),
  deletePublication: (id) => api.delete(`/api/profiles/me/publications/${id}`),

  listPatents: () => api.get('/api/profiles/me/patents'),
  addPatent: (data) => api.post('/api/profiles/me/patents', data),
  updatePatent: (id, data) => api.put(`/api/profiles/me/patents/${id}`, data),
  deletePatent: (id) => api.delete(`/api/profiles/me/patents/${id}`),
}

export const datasetService = {
  searchPublications: (q, limit = 20) =>
    api.get('/api/datasets/publications/search', { params: { q, limit } }),
  searchPatents: (q, limit = 20) =>
    api.get('/api/datasets/patents/search', { params: { q, limit } }),
}

export const fundingService = {
  list: (params = {}) => api.get('/api/funding', { params }),
  search: (q) => api.get('/api/funding/search', { params: { q } }),
  recommendations: (params = {}) => api.get('/api/funding/recommendations', { params }),
  live: (q = '') => api.get('/api/funding/live', { params: { q } }),
  get: (id) => api.get(`/api/funding/${id}`),
}

export const trendsService = {
  analyze: (query) => api.get('/api/trends', { params: { query } }),
  myDomain: () => api.get('/api/trends/my'),
}

export const patentsService = {
  landscape: (query) => api.get('/api/patents/landscape', { params: { query } }),
  myLandscape: () => api.get('/api/patents/landscape/my'),
}

export const technologyService = {
  intelligence: (query) => api.get('/api/technology/intelligence', { params: { query } }),
  myIntelligence: () => api.get('/api/technology/intelligence/my'),
}

export const innovationService = {
  myAssessment: () => api.get('/api/innovation/assessment/my'),
  assessment: (query) => api.get('/api/innovation/assessment', { params: { query } }),
  assessmentFor: (userId) => api.get(`/api/innovation/assessment/user/${userId}`),
}

export const commercializationService = {
  mine: () => api.get('/api/commercialization/my'),
  forQuery: (query) => api.get('/api/commercialization', { params: { query } }),
}

const reportParams = ({ query, subjectId } = {}) => ({
  ...(query ? { query } : {}),
  ...(subjectId ? { subject_id: subjectId } : {}),
})

export const reportService = {
  catalogue: () => api.get('/api/reports'),
  preview: (kind, opts) => api.get(`/api/reports/${kind}`,
    { params: reportParams(opts) }),

  download: async (kind, format, opts) => {
    const res = await api.get(`/api/reports/${kind}`, {
      params: { format, ...reportParams(opts) },
      responseType: 'blob',
    })
    const match = /filename="([^"]+)"/.exec(res.headers['content-disposition'] || '')
    const name = match ? match[1] : `${kind}.${format}`
    const url = URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.download = name
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    return name
  },
}

export const notificationService = {
  feed: (params = {}) => api.get('/api/notifications', { params }),
  unreadCount: () => api.get('/api/notifications/unread-count'),
  markRead: (id) => api.put(`/api/notifications/${id}/read`),
  markAllRead: () => api.post('/api/notifications/read-all'),
  dismiss: (id) => api.delete(`/api/notifications/${id}`),
  broadcast: (data) => api.post('/api/notifications/broadcast', data),
  announcements: () => api.get('/api/notifications/announcements'),
  editAnnouncement: (key, data) =>
    api.patch(`/api/notifications/announcements/${encodeURIComponent(key)}`, data),
  withdrawAnnouncement: (key) =>
    api.delete(`/api/notifications/announcements/${encodeURIComponent(key)}`),
}

export const adminService = {
  listUsers: () => api.get('/api/users/all'),
  recommendationStats: () => api.get('/api/users/analytics/recommendations'),
  pipelineStats: () => api.get('/api/users/analytics/pipeline'),
  changeRole: (userId, role) => api.put(`/api/users/${userId}/role`, { role }),
  setSuperuser: (userId, isSuperuser) =>
    api.put(`/api/users/${userId}/superuser`, { is_superuser: isSuperuser }),
  auditLog: (limit = 20) => api.get('/api/users/audit', { params: { limit } }),
  getUserProfile: (userId) => api.get(`/api/profiles/${userId}`),
  deleteUser: (userId) => api.delete(`/api/users/${userId}`),

  createOpportunity: (data) => api.post('/api/funding', data),
  updateOpportunity: (id, data) => api.put(`/api/funding/${id}`, data),
  deleteOpportunity: (id) => api.delete(`/api/funding/${id}`),
  dataHealth: () => api.get('/api/admin/data-health'),

  passwordResets: () => api.get('/api/admin/password-resets'),
  waitingResets: () => api.get('/api/admin/password-resets/waiting'),
  approveReset: (id) => api.post(`/api/admin/password-resets/${id}/approve`),
  cancelReset: (id) => api.post(`/api/admin/password-resets/${id}/cancel`),
}

export const extractErrorMessage = (err, defaultMsg = 'An error occurred') => {
  const detail = err.response?.data?.detail
  if (!detail) {
    return err.response?.data?.message || err.message || defaultMsg
  }
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const field = d.loc ? d.loc[d.loc.length - 1] : ''
      return field ? `${field}: ${d.msg}` : d.msg
    }).join(', ')
  }
  if (typeof detail === 'object') {
    return JSON.stringify(detail)
  }
  return defaultMsg
}

export default api
