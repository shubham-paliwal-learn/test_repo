import { reactive } from 'vue'

const TOKEN_KEY = 'tma_token'
const USER_KEY = 'tma_user'

export const auth = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),

  get isAuthenticated() {
    return !!this.token
  },
  get role() {
    return this.user?.role || ''
  },
  setSession(payload) {
    this.token = payload.token
    this.user = payload.user
    localStorage.setItem(TOKEN_KEY, this.token)
    localStorage.setItem(USER_KEY, JSON.stringify(this.user))
  },
  setUser(user) {
    this.user = user
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
  clear() {
    this.token = ''
    this.user = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
})

// The backend returns { success, message, data, errors }.
async function request(path, { method = 'GET', body, params, raw = false } = {}) {
  const url = new URL(path.startsWith('/') ? path : `/${path}`, window.location.origin)
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  })

  const headers = {}
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (raw) {
    if (!res.ok) throw new Error('Request failed')
    return res.blob()
  }

  let json
  try {
    json = await res.json()
  } catch {
    json = { success: false, message: `Unexpected server response (${res.status})`, errors: {} }
  }

  if (res.status === 401 && auth.token) {
    auth.clear()
    window.location.hash = '#/login'
  }
  if (!json.success) {
    const err = new Error(json.message || 'Request failed')
    err.errors = json.errors || {}
    err.status = res.status
    throw err
  }
  return json
}

export const api = {
  // ---- auth -------------------------------------------------------------
  login: (payload) => request('/api/auth/login', { method: 'POST', body: payload }),
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload }),
  me: () => request('/api/auth/me'),
  updateProfile: (payload) => request('/api/auth/profile', { method: 'PUT', body: payload }),
  logout: () => request('/api/auth/logout', { method: 'POST', body: {} }),

  // ---- treks ------------------------------------------------------------
  treks: (params) => request('/api/treks/', { params }),
  trekFilters: () => request('/api/treks/filters'),
  trek: (id, params) => request(`/api/treks/${id}`, { params }),
  trekParticipants: (id, params) => request(`/api/treks/${id}/participants`, { params }),
  createTrek: (payload) => request('/api/treks/', { method: 'POST', body: payload }),
  updateTrek: (id, payload) => request(`/api/treks/${id}`, { method: 'PUT', body: payload }),
  deleteTrek: (id) => request(`/api/treks/${id}`, { method: 'DELETE' }),
  updateTrekSlots: (id, payload) => request(`/api/treks/${id}/slots`, { method: 'PATCH', body: payload }),
  updateTrekStatus: (id, payload) => request(`/api/treks/${id}/status`, { method: 'PATCH', body: payload }),
  assignStaff: (id, payload) => request(`/api/treks/${id}/staff`, { method: 'POST', body: payload }),
  unassignStaff: (id, staffId) => request(`/api/treks/${id}/staff/${staffId}`, { method: 'DELETE' }),

  // ---- bookings ---------------------------------------------------------
  bookTrek: (payload) => request('/api/bookings/', { method: 'POST', body: payload }),
  myBookings: (params) => request('/api/bookings/my', { params }),
  allBookings: (params) => request('/api/admin/all-bookings', { params }),
  cancelBooking: (id) => request(`/api/bookings/${id}/cancel`, { method: 'PATCH', body: {} }),
  setBookingStatus: (id, payload) => request(`/api/bookings/${id}/status`, { method: 'PATCH', body: payload }),
  payBooking: (id, payload) => request(`/api/bookings/${id}/payment`, { method: 'PATCH', body: payload }),
  exportBookings: (userId) =>
    request('/api/bookings/export', { method: 'POST', body: {}, params: userId ? { user_id: userId } : {} }),
  exportStatus: (taskId) => request(`/api/bookings/export/${taskId}`),
  downloadExport: (taskId) => request(`/api/bookings/download/${taskId}`, { raw: true }),

  // ---- admin ------------------------------------------------------------
  adminDashboard: (refresh) => request('/api/admin/dashboard', { params: refresh ? { refresh: 1 } : {} }),
  adminAnalytics: () => request('/api/admin/analytics'),
  adminStaff: (params) => request('/api/admin/staff', { params }),
  createStaff: (payload) => request('/api/admin/staff', { method: 'POST', body: payload }),
  updateStaff: (id, payload) => request(`/api/admin/staff/${id}`, { method: 'PUT', body: payload }),
  setStaffStatus: (id, payload) => request(`/api/admin/staff/${id}/status`, { method: 'PATCH', body: payload }),
  adminUsers: (params) => request('/api/admin/users', { params }),
  userDetail: (id) => request(`/api/admin/users/${id}`),
  setUserStatus: (id, payload) => request(`/api/admin/users/${id}/status`, { method: 'PATCH', body: payload }),
  adminAssignments: (params) => request('/api/admin/assignments', { params }),
  adminSearch: (q) => request('/api/admin/search', { params: { q } }),
  monthlyReport: (month) => request('/api/admin/reports/monthly', { params: month ? { month } : {} }),
  triggerJob: (name) => request(`/api/admin/jobs/${name}`, { method: 'POST', body: {} }),
  jobRuns: () => request('/api/admin/jobs'),
  clearCache: () => request('/api/admin/cache', { method: 'DELETE' }),

  // ---- staff ------------------------------------------------------------
  staffDashboard: (refresh) => request('/api/staff/dashboard', { params: refresh ? { refresh: 1 } : {} }),
  staffTreks: (params) => request('/api/staff/treks', { params }),
  staffRoster: (trekId, params) => request(`/api/staff/treks/${trekId}/roster`, { params }),

  // ---- notifications (all roles) ---------------------------------------
  notifications: (params) => request('/api/admin/notifications', { params }),
  markNotificationsRead: () => request('/api/admin/notifications/read-all', { method: 'PATCH', body: {} }),
  deleteNotification: (id) => request(`/api/admin/notifications/${id}`, { method: 'DELETE' }),
}
