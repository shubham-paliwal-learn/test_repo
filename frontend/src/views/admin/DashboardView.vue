<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/client'
import { toastErr, toastOk } from '../../store'
import StatCard from '../../components/StatCard.vue'
import ChartBox from '../../components/ChartBox.vue'
import { fmtDate, fmtMoney, statusClass } from '../../utils/format'

const dash = ref(null)
const analytics = ref(null)
const loading = ref(true)

async function load(refresh = false) {
  loading.value = true
  try {
    const [d, a] = await Promise.all([api.adminDashboard(refresh), api.adminAnalytics()])
    dash.value = d.data
    analytics.value = a.data
    if (refresh) toastOk('Cache bypassed and dashboard refreshed')
  } catch (e) {
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}

// ---- chart data -------------------------------------------------------------
const statusChart = computed(() => {
  const counts = dash.value?.trek_status_counts || {}
  return {
    labels: Object.keys(counts),
    datasets: [{
      label: 'Treks',
      data: Object.values(counts),
      backgroundColor: ['#6c757d', '#0dcaf0', '#198754', '#ffc107', '#0d6efd'],
      borderRadius: 6,
    }],
  }
})

const monthlyChart = computed(() => {
  const rows = analytics.value?.monthly || []
  return {
    labels: rows.map((r) => r.label),
    datasets: [
      { label: 'Bookings', data: rows.map((r) => r.bookings), borderColor: '#1f6f43', backgroundColor: 'rgba(31,111,67,.15)', fill: true, tension: 0.3 },
      { label: 'Participants', data: rows.map((r) => r.participants), borderColor: '#0d6efd', backgroundColor: 'rgba(13,110,253,.12)', fill: true, tension: 0.3 },
    ],
  }
})

const locationChart = computed(() => {
  const rows = analytics.value?.by_location || []
  return {
    labels: rows.map((r) => r.location),
    datasets: [{ label: 'Bookings', data: rows.map((r) => r.bookings), backgroundColor: '#1f6f43', borderRadius: 6 }],
  }
})

onMounted(() => load())
</script>

<template>
  <div v-if="loading && !dash" class="text-center py-5"><span class="spinner-border text-success"></span></div>
  <div v-else-if="dash">
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
      <div>
        <h1 class="h4 mb-0">Admin Dashboard</h1>
        <p class="small text-muted mb-0">Cache backend: <code>{{ dash.totals.cache_backend }}</code></p>
      </div>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-outline-secondary" @click="load(true)">🔄 Refresh (bypass cache)</button>
        <RouterLink class="btn btn-sm btn-success" to="/admin/reports">Reports &amp; Jobs</RouterLink>
      </div>
    </div>

    <!-- headline counters -->
    <div class="row row-cols-2 row-cols-lg-4 g-3 mb-4">
      <div class="col"><StatCard label="Total Treks" :value="dash.totals.treks" icon="⛰️" variant="primary" :hint="`${dash.totals.open_treks} open`" /></div>
      <div class="col"><StatCard label="Total Users" :value="dash.totals.users" icon="👥" variant="success" /></div>
      <div class="col"><StatCard label="Total Staff" :value="dash.totals.staff" icon="🧑‍✈️" variant="info" /></div>
      <div class="col"><StatCard label="Total Bookings" :value="dash.totals.bookings" icon="🎫" variant="warning" :hint="`${dash.totals.active_bookings} active`" /></div>
      <div class="col"><StatCard label="Completed Bookings" :value="dash.totals.completed_bookings" icon="🏁" variant="secondary" /></div>
      <div class="col"><StatCard label="Cancelled Bookings" :value="dash.totals.cancelled_bookings" icon="🚫" variant="danger" /></div>
      <div class="col"><StatCard label="Bookings This Month" :value="dash.totals.bookings_this_month" icon="📅" variant="primary" /></div>
      <div class="col"><StatCard label="Revenue" :value="fmtMoney(dash.totals.revenue)" icon="💰" variant="success" hint="Excludes cancelled bookings" /></div>
    </div>

    <!-- charts -->
    <div class="row g-3 mb-4" v-if="analytics">
      <div class="col-12 col-xl-8">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-header bg-white fw-semibold">Monthly activity (last 6 months)</div>
          <div class="card-body"><ChartBox type="line" :data="monthlyChart" :height="280" /></div>
        </div>
      </div>
      <div class="col-12 col-xl-4">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-header bg-white fw-semibold">Trek status mix</div>
          <div class="card-body"><ChartBox type="doughnut" :data="statusChart" :height="280" /></div>
        </div>
      </div>
      <div class="col-12 col-lg-6">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-header bg-white fw-semibold">Most popular treks</div>
          <ul class="list-group list-group-flush">
            <li v-for="(t, i) in dash.popular_treks" :key="t.id" class="list-group-item d-flex justify-content-between align-items-center">
              <span><span class="badge text-bg-success me-2">{{ i + 1 }}</span>{{ t.name }}
                <span class="small text-muted">· {{ t.location }}</span></span>
              <span class="small">{{ t.bookings }} bookings · {{ t.participants }} trekkers</span>
            </li>
            <li v-if="!dash.popular_treks.length" class="list-group-item text-muted small">No bookings yet.</li>
          </ul>
        </div>
      </div>
      <div class="col-12 col-lg-6">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-header bg-white fw-semibold">Bookings by location</div>
          <div class="card-body"><ChartBox type="bar" :data="locationChart" :height="220" /></div>
        </div>
      </div>
    </div>

    <!-- tables -->
    <div class="row g-3">
      <div class="col-12 col-lg-6">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-header bg-white fw-semibold">Upcoming treks</div>
          <table class="table table-sm align-middle mb-0">
            <tbody>
              <tr v-for="t in dash.upcoming_treks" :key="t.id">
                <td>
                  <div class="fw-semibold small">{{ t.name }}</div>
                  <div class="text-muted" style="font-size:.75rem">📍 {{ t.location }} · {{ t.difficulty }}</div>
                </td>
                <td class="small">{{ fmtDate(t.start_date) }}</td>
                <td><span class="badge" :class="statusClass(t.status)">{{ t.status }}</span></td>
                <td class="small text-end">{{ t.available_slots }}/{{ t.total_slots }} slots</td>
              </tr>
              <tr v-if="!dash.upcoming_treks.length"><td colspan="4" class="text-muted small">No upcoming treks.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="col-12 col-lg-6">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-header bg-white fw-semibold">Recent bookings</div>
          <table class="table table-sm align-middle mb-0">
            <tbody>
              <tr v-for="b in dash.recent_bookings" :key="b.id">
                <td>
                  <div class="fw-semibold small">{{ b.trek_name }}</div>
                  <div class="text-muted" style="font-size:.75rem">👤 {{ b.user_name }} · {{ b.participants }} pax</div>
                </td>
                <td class="small">{{ fmtDate(b.booking_date) }}</td>
                <td><span class="badge" :class="statusClass(b.status)">{{ b.status }}</span></td>
                <td class="small text-end">{{ fmtMoney(b.amount) }}</td>
              </tr>
              <tr v-if="!dash.recent_bookings.length"><td colspan="4" class="text-muted small">No bookings yet.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
