<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../../api/client'
import { toastErr, toastOk } from '../../store'
import PaginatedTable from '../../components/PaginatedTable.vue'
import { fmtDate, fmtMoney, paymentClass, statusClass, downloadBlob } from '../../utils/format'

const rows = ref([])
const pagination = ref(null)
const loading = ref(true)
const trekOptions = ref([])

const filters = reactive({ status: '', trek_id: '', page: 1, per_page: 20 })

async function load() {
  loading.value = true
  try {
    const res = await api.allBookings({ ...filters })
    rows.value = res.data.items
    pagination.value = res.data.pagination
  } catch (e) {
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}

async function loadTreks() {
  try {
    const res = await api.treks({ all: 1, per_page: 100, refresh: '' })
    trekOptions.value = res.data.items
  } catch { /* optional */ }
}

async function setStatus(booking, status) {
  try {
    await api.setBookingStatus(booking.id, { status })
    toastOk(`Booking marked as ${status}`)
    load()
  } catch (e) { toastErr(e.message) }
}

async function exportAll(user_id) {
  try {
    const res = await api.exportBookings(user_id)
    const taskId = res.data?.task_id
    toastOk(res.message || 'Export job started — downloading when ready')
    if (taskId) pollAndDownload(taskId)
  } catch (e) { toastErr(e.message) }
}

async function pollAndDownload(taskId) {
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 1200))
    try {
      const res = await api.exportStatus(taskId)
      const state = res.data.state
      if (state === 'SUCCESS') {
        const blob = await api.downloadExport(taskId)
        downloadBlob(blob, `tma-bookings-${taskId.slice(0, 8)}.csv`)
        toastOk('CSV downloaded')
        return
      }
      if (state === 'FAILURE') { toastErr('Export failed on the worker.'); return }
    } catch { /* keep polling */ }
  }
  toastErr('Export is taking longer than expected. Check again shortly.')
}

function onPage(page) {
  filters.page = page
  load()
}

onMounted(() => {
  loadTreks()
  load()
})
</script>

<template>
  <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
    <div>
      <h1 class="h4 mb-0">All Bookings</h1>
      <p class="small text-muted mb-0">Complete booking history across every trek.</p>
    </div>
    <button class="btn btn-sm btn-outline-success" @click="exportAll()">📄 Export all bookings (CSV)</button>
  </div>

  <div class="card border-0 shadow-sm rounded-4 mb-3">
    <div class="card-body row g-2">
      <div class="col-12 col-md-4">
        <select v-model="filters.trek_id" class="form-select form-select-sm" @change="load">
          <option value="">All treks</option>
          <option v-for="t in trekOptions" :key="t.id" :value="String(t.id)">{{ t.name }}</option>
        </select>
      </div>
      <div class="col-12 col-md-3">
        <select v-model="filters.status" class="form-select form-select-sm" @change="load">
          <option value="">All statuses</option>
          <option>Booked</option><option>Cancelled</option><option>Completed</option>
        </select>
      </div>
    </div>
  </div>

  <div class="table-responsive card border-0 shadow-sm rounded-4">
    <table class="table table-hover align-middle mb-0">
      <thead class="table-light">
        <tr>
          <th>Booking</th><th>Trek</th><th>Trekker</th><th>Date</th><th>Pax / Amount</th>
          <th>Status</th><th>Payment</th><th class="text-end">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading"><td colspan="8" class="text-center py-4"><span class="spinner-border spinner-border-sm text-success"></span></td></tr>
        <template v-else>
          <tr v-for="b in rows" :key="b.id">
            <td class="small fw-semibold">{{ b.booking_id }}</td>
            <td>
              <div class="small fw-semibold">{{ b.trek_name }}</div>
              <div class="text-muted" style="font-size:.75rem">📍 {{ b.trek_location }} · starts {{ fmtDate(b.trek_start_date) }}</div>
            </td>
            <td>
              <div class="small">{{ b.user_name }}</div>
              <div class="text-muted" style="font-size:.75rem">{{ b.user_email }}</div>
              <button class="btn btn-link btn-sm p-0" @click="exportAll(b.user_id)" title="Export this user's history">history csv ↓</button>
            </td>
            <td class="small">{{ fmtDate(b.booking_date) }}</td>
            <td class="small">{{ b.participants }} × {{ fmtMoney(b.amount / (b.participants || 1)) }}<br />
              <strong>{{ fmtMoney(b.amount) }}</strong></td>
            <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
            <td><span class="badge" :class="paymentClass(b.payment_status)">{{ b.payment_status }}</span></td>
            <td class="text-end">
              <div class="btn-group btn-group-sm">
                <button v-if="b.status === 'Booked'" class="btn btn-outline-secondary" @click="setStatus(b, 'Completed')">Complete</button>
                <button v-if="b.status === 'Booked'" class="btn btn-outline-danger" @click="setStatus(b, 'Cancelled')">Cancel</button>
              </div>
            </td>
          </tr>
          <tr v-if="!rows.length"><td colspan="8" class="text-muted small text-center py-4">No bookings found.</td></tr>
        </template>
      </tbody>
    </table>
    <PaginatedTable :pagination="pagination" @update="onPage" />
  </div>
</template>
