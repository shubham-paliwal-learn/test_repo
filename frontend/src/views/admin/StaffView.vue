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
    const res = await api.adminStaff({ ...filters })
    rows.value = res.data.items
    pagination.value = res.data.pagination
  } catch (e) {
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}

// ---- add / edit staff --------------------------------------------------------
const showModal = ref(false)
const editing = ref(null) // null => create
const saving = ref(false)
const fieldErrors = ref({})
const form = reactive({
  full_name: '', username: '', email: '', phone: '',
  specialization: '', contact_details: '', password: '',
})

function openCreate() {
  editing.value = null
  Object.assign(form, { full_name: '', username: '', email: '', phone: '', specialization: '', contact_details: '', password: '' })
  fieldErrors.value = {}
  showModal.value = true
}

function openEdit(staff) {
  editing.value = staff
  Object.assign(form, {
    full_name: staff.full_name,
    username: staff.username,
    email: staff.email,
    phone: staff.phone || '',
    specialization: staff.specialization || '',
    contact_details: staff.contact_details || '',
    password: '',
  })
  fieldErrors.value = {}
  showModal.value = true
}

async function save() {
  saving.value = true
  fieldErrors.value = {}
  try {
    if (editing.value) {
      const payload = {
        full_name: form.full_name,
        phone: form.phone,
        specialization: form.specialization,
        contact_details: form.contact_details,
      }
      if (form.password) payload.password = form.password
      await api.updateStaff(editing.value.id, payload)
      toastOk('Staff profile updated')
    } else {
      await api.createStaff({ ...form })
      toastOk('Trek staff created — they can now log in')
    }
    showModal.value = false
    load()
  } catch (e) {
    fieldErrors.value = e.errors || {}
    toastErr(e.message)
  } finally {
    saving.value = false
  }
}

// ---- status (deactivate / blacklist / activate) ------------------------------
async function setStatus(staff, status) {
  const reason = status === 'Active' ? '' : prompt(`Reason for marking ${staff.full_name} as ${status} (optional):`)
  if (reason === null) return
  try {
    await api.setStaffStatus(staff.id, { status, reason: reason || undefined })
    toastOk(`${staff.full_name} is now ${status}`)
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
  <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
    <div>
      <h1 class="h4 mb-0">Trek Staff</h1>
      <p class="small text-muted mb-0">Staff accounts are created by the admin only — no self registration.</p>
    </div>
    <button class="btn btn-success btn-sm" @click="openCreate">＋ Add Staff</button>
  </div>

  <div class="card border-0 shadow-sm rounded-4 mb-3">
    <div class="card-body row g-2">
      <div class="col-12 col-md-6">
        <input v-model="filters.search" class="form-control form-control-sm" placeholder="Search name / username / email…"
               @input="reloadSoon" />
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
          <th>Name</th><th>Contact</th><th>Specialization</th><th>Treks</th><th>Status</th><th class="text-end">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading"><td colspan="6" class="text-center py-4"><span class="spinner-border spinner-border-sm text-success"></span></td></tr>
        <template v-else>
          <tr v-for="s in rows" :key="s.id">
            <td>
              <div class="fw-semibold">{{ s.full_name }}</div>
              <div class="small text-muted">@{{ s.username }} · joined {{ fmtDate(s.created_at) }}</div>
            </td>
            <td class="small">{{ s.email }}<br />{{ s.phone || '—' }}</td>
            <td class="small">{{ s.specialization || '—' }}</td>
            <td class="small">{{ s.assigned_treks }} lead · {{ s.support_assignments }} support<br />
              <span class="text-muted">{{ s.active_participants }} active participants</span></td>
            <td><span class="badge" :class="statusClass(s.status)">{{ s.status }}</span></td>
            <td class="text-end">
              <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-secondary" @click="openEdit(s)">Edit</button>
                <button v-if="s.status !== 'Active'" class="btn btn-outline-success" @click="setStatus(s, 'Active')">Activate</button>
                <button v-if="s.status === 'Active'" class="btn btn-outline-warning" @click="setStatus(s, 'Deactivated')">Deactivate</button>
                <button v-if="s.status !== 'Blacklisted'" class="btn btn-outline-danger" @click="setStatus(s, 'Blacklisted')">Blacklist</button>
              </div>
            </td>
          </tr>
          <tr v-if="!rows.length"><td colspan="6" class="text-muted small text-center py-4">No staff found.</td></tr>
        </template>
      </tbody>
    </table>
    <PaginatedTable :pagination="pagination" @update="onPage" />
  </div>

  <!-- create/edit modal -->
  <div v-if="showModal" class="modal d-block" tabindex="-1" style="background: rgba(0,0,0,.5)">
    <div class="modal-dialog modal-dialog-centered">
      <form class="modal-content" @submit.prevent="save">
        <div class="modal-header">
          <h5 class="modal-title">{{ editing ? `Edit staff — ${editing.full_name}` : 'Add new trek staff' }}</h5>
          <button type="button" class="btn-close" @click="showModal = false"></button>
        </div>
        <div class="modal-body row g-3">
          <div class="col-12">
            <label class="form-label small">Full name *</label>
            <input v-model.trim="form.full_name" class="form-control" :class="{ 'is-invalid': fieldErrors.full_name }" required minlength="3" maxlength="120" />
            <div class="invalid-feedback d-block">{{ fieldErrors.full_name }}</div>
          </div>
          <template v-if="!editing">
            <div class="col-12 col-md-6">
              <label class="form-label small">Username *</label>
              <input v-model.trim="form.username" class="form-control" :class="{ 'is-invalid': fieldErrors.username }"
                     required minlength="3" maxlength="64" pattern="[A-Za-z0-9._]+" />
              <div class="invalid-feedback d-block">{{ fieldErrors.username }}</div>
            </div>
            <div class="col-12 col-md-6">
              <label class="form-label small">Email *</label>
              <input v-model.trim="form.email" type="email" class="form-control" :class="{ 'is-invalid': fieldErrors.email }" required />
              <div class="invalid-feedback d-block">{{ fieldErrors.email }}</div>
            </div>
            <div class="col-12">
              <label class="form-label small">Password * (min 8 chars)</label>
              <input v-model="form.password" type="password" class="form-control" :class="{ 'is-invalid': fieldErrors.password }"
                     required minlength="8" autocomplete="new-password" />
              <div class="invalid-feedback d-block">{{ fieldErrors.password }}</div>
            </div>
          </template>
          <div class="col-12 col-md-6">
            <label class="form-label small">Phone</label>
            <input v-model.trim="form.phone" type="tel" class="form-control" :class="{ 'is-invalid': fieldErrors.phone }"
                   pattern="[0-9+ ()-]{8,20}" />
            <div class="invalid-feedback d-block">{{ fieldErrors.phone }}</div>
          </div>
          <div class="col-12 col-md-6">
            <label class="form-label small">Specialization</label>
            <input v-model.trim="form.specialization" class="form-control" maxlength="80" placeholder="e.g. High-altitude lead" />
          </div>
          <div class="col-12">
            <label class="form-label small">Contact details / notes</label>
            <input v-model.trim="form.contact_details" class="form-control" maxlength="200" />
          </div>
          <div v-if="editing" class="col-12">
            <label class="form-label small">Reset password (leave blank to keep)</label>
            <input v-model="form.password" type="password" class="form-control" :class="{ 'is-invalid': fieldErrors.password }"
                   minlength="8" autocomplete="new-password" />
            <div class="invalid-feedback d-block">{{ fieldErrors.password }}</div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary btn-sm" @click="showModal = false">Cancel</button>
          <button type="submit" class="btn btn-success btn-sm" :disabled="saving">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
            {{ editing ? 'Save changes' : 'Create staff' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
