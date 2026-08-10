import axios from 'axios'

const api = axios.create({ baseURL: '' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// fired when the cached user record changes, so shared UI can refresh in place
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
  logout: () => { localStorage.removeItem('token'); localStorage.removeItem('user') },

  getCachedUser: () => JSON.parse(localStorage.getItem('user') || '{}'),

  // write the cached user and notify listeners (Nav, Dashboard) in this tab
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
}

export const commercializationService = {
  mine: () => api.get('/api/commercialization/my'),
  forQuery: (query) => api.get('/api/commercialization', { params: { query } }),
}

export const adminService = {
  listUsers: () => api.get('/api/users/all'),
  changeRole: (userId, role) => api.put(`/api/users/${userId}/role`, { role }),
  getUserProfile: (userId) => api.get(`/api/profiles/${userId}`),
  deleteUser: (userId) => api.delete(`/api/users/${userId}`),
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
