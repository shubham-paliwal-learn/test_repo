<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../api/client'
import { toastErr } from '../../store'
import StatCard from '../../components/StatCard.vue'
import { fmtDate, statusClass } from '../../utils/format'

const router = useRouter()
const data = ref(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const res = await api.staffDashboard()
    data.value = res.data
  } catch (e) { toastErr(e.message) } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div v-if="loading" class="text-center py-5"><span class="spinner-border text-success"></span></div>
  <div v-else-if="data">
    <h1 class="h4 mb-1">Staff Dashboard — {{ data.staff.full_name }}</h1>
    <p class="small text-muted mb-4">{{ data.staff.specialization || 'Trek coordinator' }} · cache backend: {{ data.totals.cache_backend }}</p>

    <div class="row row-cols-2 row-cols-lg-5 g-3 mb-4">
      <div class="col"><StatCard label="Assigned treks" :value="data.totals.assigned_treks" icon="⛰️" variant="primary" /></div>
      <div class="col"><StatCard label="Upcoming" :value="data.totals.upcoming_treks" icon="🗓" variant="info" /></div>
      <div class="col"><StatCard label="Active" :value="data.totals.active_treks" icon="🟢" variant="success" /></div>
      <div class="col"><StatCard label="Completed" :value="data.totals.completed_treks" icon="🏁" variant="secondary" /></div>
      <div class="col"><StatCard label="Registered users" :value="data.totals.registered_users" icon="👥" variant="warning" /></div>
    </div>

    <h2 class="h5 mb-3">My assigned treks</h2>
    <div class="table-responsive card border-0 shadow-sm rounded-4">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr><th>Trek</th><th>Dates</th><th>Status</th><th>Booked / Total</th><th>Slots left</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="t in data.treks" :key="t.id">
            <td>
              <div class="fw-semibold">{{ t.name }}</div>
              <div class="small text-muted">📍 {{ t.location }} · {{ t.difficulty }} · {{ t.duration_days }}d</div>
            </td>
            <td class="small">{{ fmtDate(t.start_date) }} → {{ fmtDate(t.end_date) }}</td>
            <td><span class="badge" :class="statusClass(t.status)">{{ t.status }}</span></td>
            <td>{{ t.booked_count ?? '-' }} / {{ t.total_slots }}</td>
            <td><strong :class="{ 'text-danger': t.available_slots <= 0 }">{{ t.available_slots }}</strong></td>
            <td><button class="btn btn-sm btn-outline-success" @click="router.push(`/staff/treks/${t.id}`)">Manage</button></td>
          </tr>
          <tr v-if="!data.treks.length"><td colspan="6" class="text-muted small">No treks assigned yet. Ask the admin to assign you.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
