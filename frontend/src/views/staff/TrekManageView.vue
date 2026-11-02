<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../../api/client'
import { toastOk, toastErr } from '../../store'
import { fmtDate, fmtDateTime, statusClass } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const trekId = route.params.id

const trek = ref(null)
const roster = ref([])
const rosterPagination = ref(null)
const rosterSummary = ref({})
const loading = ref(true)
const saving = ref(false)

const slotForm = reactive({ total_slots: null })
const instructions = ref('')

async function loadAll() {
  loading.value = true
  try {
    const [t, r] = await Promise.all([api.trek(trekId), api.staffRoster(trekId)])
    trek.value = t.data
    slotForm.total_slots = t.data.total_slots
    instructions.value = t.data.instructions || ''
    roster.value = r.data.items
    rosterPagination.value = r.data.pagination
    rosterSummary.value = r.data.summary
  } catch (e) {
    toastErr(e.message)
    router.push('/staff')
  } finally { loading.value = false }
}
onMounted(loadAll)

async function saveSlots() {
  saving.value = true
  try {
    const res = await api.updateSlots(trekId, { total_slots: Number(slotForm.total_slots) })
    trek.value = res.data
    toastOk(res.message)
  } catch (e) { toastErr(e.message) } finally { saving.value = false }
}

async function setStatus(status) {
  if (!confirm(`Set trek status to "${status}"?`)) return
  try {
    const res = await api.updateTrekStatus(trekId, { status })
    trek.value = { ...trek.value, ...res.data }
    toastOk(res.message)
  } catch (e) { toastErr(e.message) }
}

async function saveInstructions() {
  try {
    const res = await api.updateTrek(trekId, { instructions: instructions.value })
    trek.value = { ...trek.value, ...res.data }
    toastOk('Instructions saved')
  } catch (e) { toastErr(e.message) }
}

async function markBooking(b, status) {
  try {
    const res = await api.updateBookingStatus(b.id, { status })
    b.status = res.data.status
    toastOk(res.message)
    const r = await api.staffRoster(trekId)
    roster.value = r.data.items
    rosterSummary.value = r.data.summary
  } catch (e) { toastErr(e.message) }
}
</script>

<template>
  <div v-if="loading" class="text-center py-5"><span class="spinner-border text-success"></span></div>
  <div v-else-if="trek">
    <button class="btn btn-sm btn-outline-secondary mb-3" @click="router.push('/staff')">← Back to dashboard</button>
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
      <div>
        <h1 class="h4 mb-1">{{ trek.name }} <span class="badge ms-2" :class="statusClass(trek.status)">{{ trek.status }}</span></h1>
        <p class="small text-muted mb-0">📍 {{ trek.location }} · {{ fmtDate(trek.start_date) }} → {{ fmtDate(trek.end_date) }} · Lead: {{ trek.assigned_staff_name }}</p>
      </div>
      <!-- staff workflow: Open -> Closed -> Completed -->
      <div class="btn-group">
        <button class="btn btn-sm btn-outline-success" :disabled="trek.status === 'Open'" @click="setStatus('Open')">Open bookings</button>
        <button class="btn btn-sm btn-outline-warning" :disabled="trek.status === 'Closed'" @click="setStatus('Closed')">Close bookings</button>
        <button class="btn btn-sm btn-outline-primary" :disabled="trek.status === 'Completed'" @click="setStatus('Completed')">Mark completed</button>
      </div>
    </div>

    <div class="row g-4 mb-4">
      <div class="col-md-4">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-body">
            <h2 class="h6">Slot management</h2>
            <p class="small text-muted">Booked: <strong>{{ trek.booked_count }}</strong> · Available: <strong>{{ trek.available_slots }}</strong></p>
            <form class="input-group input-group-sm" @submit.prevent="saveSlots">
              <input v-model.number="slotForm.total_slots" type="number" min="1" max="500" class="form-control" required />
              <button class="btn btn-success" :disabled="saving">Update total</button>
            </form>
            <div class="form-text">Cannot be lower than existing bookings.</div>
          </div>
        </div>
      </div>
      <div class="col-md-8">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-body">
            <h2 class="h6">Trekker instructions</h2>
            <textarea v-model="instructions" class="form-control form-control-sm" rows="3" maxlength="2000"></textarea>
            <button class="btn btn-sm btn-outline-success mt-2" @click="saveInstructions">Save instructions</button>
          </div>
        </div>
      </div>
    </div>

    <h2 class="h5 mb-2">Participant roster
      <span class="badge text-bg-success ms-2">{{ rosterSummary.booked ?? 0 }} booked</span>
      <span class="badge text-bg-primary ms-1">{{ rosterSummary.completed ?? 0 }} completed</span>
      <span class="badge text-bg-danger ms-1">{{ rosterSummary.cancelled ?? 0 }} cancelled</span>
    </h2>
    <div class="table-responsive card border-0 shadow-sm rounded-4">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr><th>Trekker</th><th>Contact</th><th>Booked on</th><th>Party</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr v-for="b in roster" :key="b.id">
            <td>
              <div class="fw-semibold">{{ b.user_name }}</div>
              <div class="small text-muted">{{ b.booking_id }}</div>
            </td>
            <td class="small">{{ b.user_email }}</td>
            <td class="small">{{ fmtDateTime(b.booking_date) }}</td>
            <td>{{ b.participants }}</td>
            <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
            <td class="d-flex gap-1">
              <button v-if="b.status === 'Booked'" class="btn btn-sm btn-outline-primary" @click="markBooking(b, 'Completed')">✔ Attended</button>
              <button v-if="b.status === 'Booked'" class="btn btn-sm btn-outline-danger" @click="markBooking(b, 'Cancelled')">✕ Cancel</button>
            </td>
          </tr>
          <tr v-if="!roster.length"><td colspan="6" class="text-muted small">No participants yet.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
