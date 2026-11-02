// Small formatting / display helpers shared by the views.

export function fmtDate(value) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtDateTime(value) {
  if (!value) return '-'
  const iso = /[TZ]/.test(value) ? value : `${value}Z` // backend stores naive UTC
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function fmtMoney(value) {
  const n = Number(value || 0)
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

const STATUS_CLASS = {
  Pending: 'bg-secondary-subtle text-secondary-emphasis',
  Approved: 'bg-info-subtle text-info-emphasis',
  Open: 'bg-success-subtle text-success-emphasis',
  Closed: 'bg-warning-subtle text-warning-emphasis',
  Completed: 'bg-primary-subtle text-primary-emphasis',
  Booked: 'bg-success-subtle text-success-emphasis',
  Cancelled: 'bg-danger-subtle text-danger-emphasis',
  Active: 'bg-success-subtle text-success-emphasis',
  Deactivated: 'bg-warning-subtle text-warning-emphasis',
  Blacklisted: 'bg-danger-subtle text-danger-emphasis',
  Paid: 'bg-success-subtle text-success-emphasis',
  Refunded: 'bg-info-subtle text-info-emphasis',
  'Not Required': 'bg-light text-muted',
}

export function statusClass(status) {
  if (!status) return 'bg-light text-muted'
  return STATUS_CLASS[status] || 'bg-light text-muted'
}

export function paymentClass(status) {
  if (!status) return 'bg-light text-muted'
  return STATUS_CLASS[status] || 'bg-secondary-subtle text-secondary-emphasis'
}

export function difficultyIcon(difficulty) {
  return { Easy: '🟢', Moderate: '🟡', Hard: '🔴' }[difficulty] || '⛰️'
}

export function slotPercent(available, total) {
  if (!total) return 0
  return Math.round(((total - available) / total) * 100)
}

export async function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
