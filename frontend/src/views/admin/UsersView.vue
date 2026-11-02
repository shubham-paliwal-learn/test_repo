<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../../api/client'
import { toastErr, toastOk } from '../../store'
import PaginatedTable from '../../components/PaginatedTable.vue'
import { fmtDate, statusClass } from '../../utils/format'

const rows = ref([])
const pagination = ref(null)
const loading = ref(true)

const filters = reactive({ search: '', status: '', page: 1, per_page: 10 })
let timer = null

function reloadSoon() {
  clearTimeout(timer)
  timer = setTimeout(load, 250)
}

async function load() {
  loading.value = true
  try {
    const res = await api.adminUsers({ ...filters })
    rows.value = res.data.items
    pagination.value = res.data.pagination
  } catch (e) {
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}

// ---- detail drawer ------------------------------------------------------------
const detail = ref(null)
const showDetail = ref(false)

async function openDetail(user) {
  showDetail.value = true
  detail.value = null
  try {
    const res = await api.userDetail(user.id)
    detail.value = res.data
  } catch (e) {
    toastErr(e.message)
    showDetail.value = false
  }
}

// ---- deactivate / blacklist ----------------------------------------------------
async function setStatus(user, status) {
  if (status !== 'Active') {
    const reason = prompt(`Reason for marking ${user.full_name} as ${status} (optional):`)
    if (reason === null) return
  }
  try {
    await api.setUserStatus(user.id, { status })
    toastOk(`${user.full_name} is now ${status}`)
    load()
  } catch (e) { toastErr(e.message) }
}

function onPage(page) {
  filters.page = page
  load()
}

onMounted(load)
</script>

<template>
  <div class="mb-3">
    <h1 class="h4 mb-0">Trekkers (Users)</h1>
    <p class="small text-muted mb-0">Search, inspect history and control account status.</p>
  </div>

  <div class="card border-0 shadow-sm rounded-4 mb-3">
    <div class="card-body row g-2">
      <div class="col-12 col-md-6">
        <input v-model="filters.search" class="form-control form-control-sm" placeholder="Search name / username / email…" @input="reloadSoon" />
      </div>
      <div class="col-12 col-md-3">
        <select v-model="filters.status" class="form-select form-select-sm" @change="load">
          <option value="">All statuses</option>
          <option>Active</option><option>Deactivated</option><option>Blacklisted</option>
        </select>
      </div>
    </div>
  </div>

  <div class="table-responsive card border-0 shadow-sm rounded-4">
    <table class="table table-hover align-middle mb-0">
      <thead class="table-light">
        <tr>
          <th>User</th><th>Contact</th><th>Bookings</th><th>Status</th><th>Joined</th><th class="text-end">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading"><td colspan="6" class="text-center py-4"><span class="spinner-border spinner-border-sm text-success"></span></td></tr>
        <template v-else>
          <tr v-for="u in rows" :key="u.id">
            <td>
              <div class="fw-semibold">{{ u.full_name }}</div>
              <div class="small text-muted">@{{ u.username }} · ID {{ u.id }}</div>
            </td>
            <td class="small">{{ u.email }}<br />{{ u.phone || '—' }}</td>
            <td class="small">{{ u.total_bookings }} total<br /><span class="text-muted">{{ u.active_bookings }} active</span></td>
            <td><span class="badge" :class="statusClass(u.status)">{{ u.status }}</span></td>
            <td class="small">{{ fmtDate(u.created_at) }}</td>
            <td class="text-end">
              <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-secondary" @click="openDetail(u)">History</button>
                <button v-if="u.status !== 'Active'" class="btn btn-outline-success" @click="setStatus(u, 'Active')">Activate</button>
                <button v-if="u.status === 'Active'" class="btn btn-outline-warning" @click="setStatus(u, 'Deactivated')">Deactivate</button>
                <button v-if="u.status !== 'Blacklisted'" class="btn btn-outline-danger" @click="setStatus(u, 'Blacklisted')">Blacklist</button>
              </div>
            </td>
          </tr>
          <tr v-if="!rows.length"><td colspan="6" class="text-muted small text-center py-4">No users found.</td></tr>
        </template>
      </tbody>
    </table>
    <PaginatedTable :pagination="pagination" @update="onPage" />
  </div>

  <!-- user history modal -->
  <div v-if="showDetail" class="modal d-block" tabindex="-1" style="background: rgba(0,0,0,.5)">
    <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            <span v-if="detail">{{ detail.full_name }} <span class="badge ms-2" :class="statusClass(detail.status)">{{ detail.status }}</span></span>
            <span v-else>Loading…</span>
          </h5>
          <button type="button" class="btn-close" @click="showDetail = false"></button>
        </div>
        <div class="modal-body">
          <template v-if="detail">
            <p class="small text-muted mb-3">@{{ detail.username }} · {{ detail.email }} · {{ detail.phone || 'no phone' }}</p>
            <h6 class="fw-semibold">Trekking history</h6>
            <table class="table table-sm">
              <thead><tr><th>Trek</th><th>Booked on</th><th>Status</th><th>Payment</th></tr></thead>
              <tbody>
                <tr v-for="b in detail.bookings" :key="b.id">
                  <td>{{ b.trek_name }}<div class="small text-muted">📍 {{ b.trek_location }} · {{ fmtDate(b.trek_start_date) }}</div></td>
                  <td class="small">{{ fmtDate(b.booking_date) }}</td>
                  <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
                  <td><span class="badge" :class="statusClass(b.payment_status)">{{ b.payment_status }}</span></td>
                </tr>
                <tr v-if="!detail.bookings.length"><td colspan="4" class="small text-muted">No bookings yet.</td></tr>
              </tbody>
            </table>
          </template>
          <div v-else class="text-center py-4"><span class="spinner-border text-success"></span></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showDetail = false">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>
