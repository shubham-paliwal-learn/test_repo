<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api/client'
import { toastOk, toastErr } from '../../store'
import { fmtDate, fmtDateTime, fmtMoney, statusClass, paymentClass, downloadBlob } from '../../utils/format'
import PaginatedTable from '../../components/PaginatedTable.vue'

const bookings = ref([])
const pagination = ref(null)
const summary = ref({})
const statusFilter = ref('')
const page = ref(1)
const loading = ref(false)

// async CSV export state
const exporting = ref(false)
const exportTask = ref(null)

async function load() {
  loading.value = true
  try {
    const res = await api.myBookings({ status: statusFilter.value || undefined, page: page.value, per_page: 10 })
    bookings.value = res.data.items
    pagination.value = res.data.pagination
    summary.value = res.data.summary
  } catch (e) { toastErr(e.message) } finally { loading.value = false }
}
onMounted(load)

function changePage(p) { page.value = p; load() }
function filterByStatus(s) { statusFilter.value = s; page.value = 1; load() }

async function cancel(b) {
  if (!confirm(`Cancel your booking for "${b.trek_name}"?`)) return
  try {
    const res = await api.cancelBooking(b.id)
    toastOk(res.message)
    load()
  } catch (e) { toastErr(e.message) }
}

async function pay(b) {
  try {
    const res = await api.payBooking(b.id, {})
    toastOk(res.message)
    load()
  } catch (e) { toastErr(e.message) }
}

// ---- user-triggered async batch job: export trekking history to CSV --------
async function startExport() {
  exporting.value = true
  exportTask.value = null
  try {
    const res = await api.exportBookings()
    exportTask.value = { task_id: res.data.task_id, state: res.data.state }
    pollExport()
  } catch (e) {
    toastErr(e.message)
    exporting.value = false
  }
}

async function pollExport() {
  if (!exportTask.value) return
  const { task_id } = exportTask.value
  try {
    const res = await api.exportStatus(task_id)
    exportTask.value = res.data
    if (res.data.state === 'SUCCESS') {
      toastOk('Your trekking history CSV is ready — downloading now.')
      const blob = await api.downloadExport(task_id)
      downloadBlob(blob, `tma-trek-history-${task_id.slice(0, 8)}.csv`)
      exporting.value = false
      return
    }
    if (res.data.state === 'FAILURE') { toastErr('Export failed. Please retry.'); exporting.value = false; return }
    setTimeout(pollExport, 1200)
  } catch (e) {
    // result backend may not be ready yet — keep polling briefly
    setTimeout(pollExport, 1500)
  }
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="h4 mb-0">🎒 My Bookings & Trekking History</h1>
      <button class="btn btn-outline-success btn-sm" :disabled="exporting" @click="startExport">
        <span v-if="exporting" class="spinner-border spinner-border-sm me-1"></span>
        {{ exporting ? `Exporting… (${exportTask?.state || 'PENDING'})` : '⬇ Export history (CSV)' }}
      </button>
    </div>

    <div class="row row-cols-2 row-cols-md-4 g-3 mb-4">
      <div class="col"><button class="btn btn-light stat-card w-100 text-start" @click="filterByStatus('')">Total: <strong>{{ summary.total ?? '-' }}</strong></button></div>
      <div class="col"><button class="btn btn-light stat-card w-100 text-start" @click="filterByStatus('Booked')">Active: <strong>{{ summary.booked ?? '-' }}</strong></button></div>
      <div class="col"><button class="btn btn-light stat-card w-100 text-start" @click="filterByStatus('Completed')">Completed: <strong>{{ summary.completed ?? '-' }}</strong></button></div>
      <div class="col"><button class="btn btn-light stat-card w-100 text-start" @click="filterByStatus('Cancelled')">Cancelled: <strong>{{ summary.cancelled ?? '-' }}</strong></button></div>
    </div>

    <div v-if="loading" class="text-center py-5"><span class="spinner-border text-success"></span></div>
    <div v-else-if="!bookings.length" class="alert alert-info">No bookings yet. Head over to <RouterLink to="/user/treks">Explore Treks</RouterLink> to book your first adventure!</div>

    <div v-else class="table-responsive card border-0 shadow-sm rounded-4">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th>Booking</th><th>Trek</th><th>Starts</th><th>Party</th><th>Amount</th>
            <th>Status</th><th>Payment</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bookings" :key="b.id">
            <td>
              <div class="fw-semibold">{{ b.booking_id }}</div>
              <div class="small text-muted">{{ fmtDateTime(b.booking_date) }}</div>
            </td>
            <td>
              <div class="fw-semibold">{{ b.trek_name }}</div>
              <div class="small text-muted">📍 {{ b.trek_location }}</div>
            </td>
            <td>{{ fmtDate(b.trek_start_date) }}</td>
            <td>{{ b.participants }}</td>
            <td>{{ fmtMoney(b.amount) }}</td>
            <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
            <td><span class="badge" :class="paymentClass(b.payment_status)">{{ b.payment_status }}</span></td>
            <td class="d-flex gap-1">
              <button v-if="b.status === 'Booked' && b.payment_status === 'Pending'" class="btn btn-sm btn-outline-success" @click="pay(b)">Pay</button>
              <button v-if="b.status === 'Booked'" class="btn btn-sm btn-outline-danger" @click="cancel(b)">Cancel</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <PaginatedTable :pagination="pagination" @update="changePage" />
  </div>
</template>
