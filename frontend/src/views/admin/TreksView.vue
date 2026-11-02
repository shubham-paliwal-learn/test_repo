<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../api/client'
import { toastErr, toastOk } from '../../store'
import PaginatedTable from '../../components/PaginatedTable.vue'
import { difficultyIcon, fmtDate, slotPercent, statusClass } from '../../utils/format'

const router = useRouter()

const rows = ref([])
const pagination = ref(null)
const filtersOptions = ref({ difficulties: [], statuses: [], locations: [] })
const loading = ref(true)
const staffOptions = ref([])

const filters = reactive({
  search: '',
  difficulty: '',
  location: '',
  status: '',
  min_duration: '',
  max_duration: '',
  only_available: '',
  sort_by: 'start_date',
  order: 'asc',
  page: 1,
  per_page: 10,
})

let searchTimer = null
watch(filters, () => {
  // debounce text search, reload immediately for other filters
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 250)
}, { deep: true })

async function load() {
  loading.value = true
  try {
    const res = await api.treks({ ...filters, all: 1, refresh: '' })
    rows.value = res.data.items
    pagination.value = res.data.pagination
  } catch (e) {
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}

async function loadFilters() {
  try {
    const res = await api.trekFilters()
    filtersOptions.value = res.data
  } catch { /* non critical */ }
}

async function loadStaff() {
  try {
    const res = await api.adminStaff({ per_page: 100, status: 'Active' })
    staffOptions.value = res.data.items
  } catch { /* non critical */ }
}

// ---- quick actions ----------------------------------------------------------
async function setStatus(trek, status) {
  try {
    await api.updateTrekStatus(trek.id, { status })
    toastOk(`Trek marked as ${status}`)
    load()
  } catch (e) { toastErr(e.message) }
}

async function removeTrek(trek) {
  if (!confirm(`Delete trek "${trek.name}"? This cannot be undone.`)) return
  try {
    await api.deleteTrek(trek.id)
    toastOk('Trek removed')
    load()
  } catch (e) { toastErr(e.message) }
}

const assignTarget = ref(null)
const assignStaffId = ref('')
const showAssignModal = ref(false)

function openAssign(trek) {
  assignTarget.value = trek
  assignStaffId.value = String(trek.assigned_staff_id || '')
  showAssignModal.value = true
}

async function saveAssign() {
  if (!assignTarget.value) return
  try {
    if (assignStaffId.value) {
      await api.assignStaff(assignTarget.value.id, { staff_id: Number(assignStaffId.value) })
      toastOk('Staff assigned to trek')
    } else {
      if (assignTarget.value.assigned_staff_id) {
        await api.unassignStaff(assignTarget.value.id, assignTarget.value.assigned_staff_id)
      }
      toastOk('Staff unassigned from trek')
    }
    showAssignModal.value = false
    load()
  } catch (e) { toastErr(e.message) }
}

function onPage(page) {
  filters.page = page
  load()
}

onMounted(() => {
  loadFilters()
  loadStaff()
  load()
})
</script>

<template>
  <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
    <div>
      <h1 class="h4 mb-0">Manage Treks</h1>
      <p class="small text-muted mb-0">Create routes, approve/open them and assign staff.</p>
    </div>
    <RouterLink class="btn btn-success btn-sm" to="/admin/treks/new">＋ New Trek</RouterLink>
  </div>

  <!-- filters -->
  <div class="card border-0 shadow-sm rounded-4 mb-3">
    <div class="card-body row g-2 align-items-end">
      <div class="col-12 col-md-3">
        <label class="form-label small mb-1">Search</label>
        <input v-model="filters.search" class="form-control form-control-sm" placeholder="Name / location…" />
      </div>
      <div class="col-6 col-md-2">
        <label class="form-label small mb-1">Difficulty</label>
        <select v-model="filters.difficulty" class="form-select form-select-sm">
          <option value="">All</option>
          <option v-for="d in filtersOptions.difficulties" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <div class="col-6 col-md-2">
        <label class="form-label small mb-1">Location</label>
        <select v-model="filters.location" class="form-select form-select-sm">
          <option value="">All</option>
          <option v-for="l in filtersOptions.locations" :key="l" :value="l">{{ l }}</option>
        </select>
      </div>
      <div class="col-6 col-md-2">
        <label class="form-label small mb-1">Status</label>
        <select v-model="filters.status" class="form-select form-select-sm">
          <option value="">All</option>
          <option v-for="s in filtersOptions.statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="col-6 col-md-1">
        <label class="form-label small mb-1">Min days</label>
        <input v-model="filters.min_duration" type="number" min="1" class="form-control form-control-sm" />
      </div>
      <div class="col-6 col-md-1">
        <label class="form-label small mb-1">Max days</label>
        <input v-model="filters.max_duration" type="number" min="1" class="form-control form-control-sm" />
      </div>
      <div class="col-12 col-md-1 d-flex align-items-center">
        <div class="form-check">
          <input v-model="filters.only_available" class="form-check-input" type="checkbox" true-value="1" false-value="" id="availChk" />
          <label class="form-check-label small" for="availChk">Slots left</label>
        </div>
      </div>
    </div>
  </div>

  <!-- table -->
  <div class="table-responsive card border-0 shadow-sm rounded-4">
    <table class="table table-hover align-middle mb-0">
      <thead class="table-light">
        <tr>
          <th>Trek</th>
          <th>Dates</th>
          <th>Status</th>
          <th>Slots</th>
          <th>Staff</th>
          <th class="text-end">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading"><td colspan="6" class="text-center py-4"><span class="spinner-border spinner-border-sm text-success"></span></td></tr>
        <template v-else>
          <tr v-for="t in rows" :key="t.id">
            <td>
              <div class="fw-semibold">{{ difficultyIcon(t.difficulty) }} {{ t.name }}</div>
              <div class="small text-muted">📍 {{ t.location }} · {{ t.difficulty }} · {{ t.duration_days }}d · ₹{{ t.base_price }}</div>
            </td>
            <td class="small">{{ fmtDate(t.start_date) }}<br />→ {{ fmtDate(t.end_date) }}</td>
            <td><span class="badge" :class="statusClass(t.status)">{{ t.status }}</span></td>
            <td style="min-width: 110px">
              <div class="small">{{ t.available_slots }}/{{ t.total_slots }} booked {{ t.booked_count ?? 0 }}</div>
              <div class="progress slot-bar mt-1">
                <div class="progress-bar bg-success" :style="{ width: `${100 - slotPercent(t.available_slots, t.total_slots)}%` }"></div>
              </div>
            </td>
            <td class="small">{{ t.assigned_staff_name || '—' }}</td>
            <td class="text-end">
              <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-secondary" @click="router.push(`/admin/treks/${t.id}/edit`)">Edit</button>
                <button class="btn btn-outline-primary" @click="openAssign(t)">Assign staff</button>
                <button v-if="t.status === 'Pending'" class="btn btn-outline-info" @click="setStatus(t, 'Approved')">Approve</button>
                <button v-if="t.status === 'Approved'" class="btn btn-outline-success" @click="setStatus(t, 'Open')">Open</button>
                <button v-if="t.status === 'Open'" class="btn btn-outline-warning" @click="setStatus(t, 'Closed')">Close</button>
                <button v-if="t.status !== 'Completed'" class="btn btn-outline-secondary" @click="setStatus(t, 'Completed')">Complete</button>
                <button class="btn btn-outline-danger" @click="removeTrek(t)">Delete</button>
              </div>
            </td>
          </tr>
          <tr v-if="!rows.length"><td colspan="6" class="text-muted small text-center py-4">No treks match the current filters.</td></tr>
        </template>
      </tbody>
    </table>
    <PaginatedTable :pagination="pagination" @update="onPage" />
  </div>

  <!-- assign staff modal -->
  <div v-if="showAssignModal" class="modal d-block" tabindex="-1" style="background: rgba(0,0,0,.5)">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Assign staff — {{ assignTarget?.name }}</h5>
          <button type="button" class="btn-close" @click="showAssignModal = false"></button>
        </div>
        <div class="modal-body">
          <label class="form-label small">Lead staff member</label>
          <select v-model="assignStaffId" class="form-select">
            <option value="">— Unassigned —</option>
            <option v-for="s in staffOptions" :key="s.id" :value="String(s.id)">{{ s.full_name }} ({{ s.specialization || 'staff' }})</option>
          </select>
          <p class="small text-muted mt-2 mb-0">The lead coordinator receives management rights over slots, status and rosters.</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showAssignModal = false">Cancel</button>
          <button class="btn btn-success btn-sm" @click="saveAssign">Save assignment</button>
        </div>
      </div>
    </div>
  </div>
</template>
