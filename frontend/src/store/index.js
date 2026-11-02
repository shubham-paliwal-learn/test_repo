import { reactive, watch } from 'vue'
import { api, auth } from '../api/client'

/** Global toast notifications (Bootstrap styled). */
export const toasts = reactive({ items: [] })
let toastSeq = 0

export function pushToast(message, variant = 'success', delay = 4200) {
  const id = ++toastSeq
  toasts.items.push({ id, message, variant })
  setTimeout(() => removeToast(id), delay)
}

export function removeToast(id) {
  const idx = toasts.items.findIndex((t) => t.id === id)
  if (idx !== -1) toasts.items.splice(idx, 1)
}

export const toastOk = (m) => pushToast(m, 'success')
export const toastErr = (m) => pushToast(m, 'danger', 6000)

/** Shared UI state: in-app notification bell + admin global search. */
export const ui = reactive({
  unread: 0,
  notifications: [],
  searchResults: null,
  searching: false,
})

async function refreshNotifications() {
  if (!auth.isAuthenticated) {
    ui.unread = 0
    ui.notifications = []
    return
  }
  try {
    const res = await api.notifications({ include_read: 'false' })
    ui.notifications = res.data.items || []
    ui.unread = res.data.unread || 0
  } catch {
    /* silent – the bell is non-critical */
  }
}

watch(() => auth.token, refreshNotifications)
if (auth.isAuthenticated) refreshNotifications()
setInterval(refreshNotifications, 30000)

export async function markAllRead() {
  try {
    await api.markNotificationsRead()
    await refreshNotifications()
  } catch (e) {
    toastErr(e.message)
  }
}

export async function deleteNotification(id) {
  try {
    await api.deleteNotification(id)
    await refreshNotifications()
  } catch (e) {
    toastErr(e.message)
  }
}

/** Convenience wrapper: run an API call, show a toast on error, return data. */
export async function run(fn, { okMessage } = {}) {
  try {
    const res = await fn()
    if (okMessage) pushToast(okMessage, 'success')
    return res
  } catch (e) {
    pushToast(e.message || 'Something went wrong', 'danger', 6000)
    throw e
  }
}
