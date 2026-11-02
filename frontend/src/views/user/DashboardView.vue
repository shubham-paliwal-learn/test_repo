<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, auth } from '../../api/client'
import { toastErr } from '../../store'
import StatCard from '../../components/StatCard.vue'
import TrekCard from '../../components/TrekCard.vue'
import { fmtDate, statusClass } from '../../utils/format'

const router = useRouter()
const summary = ref({})
const bookings = ref([])
const recommended = ref([])

onMounted(async () => {
  try {
    const [b, t] = await Promise.all([api.myBookings({ per_page: 5 }), api.treks({ upcoming: 1, only_available: 1, per_page: 4 })])
    summary.value = b.data.summary || {}
    bookings.value = b.data.items
    recommended.value = t.data.items
  } catch (e) { toastErr(e.message) }
})

function book(trek) { router.push(`/user/treks/${trek.id}`) }
</script>

<template>
  <div>
    <h1 class="h4 mb-1">Welcome back, {{ auth.user?.full_name }} 👋</h1>
    <p class="text-muted small mb-4">Here is your trekking snapshot. Ready for the next adventure?</p>

    <div class="row row-cols-2 row-cols-lg-4 g-3 mb-4">
      <div class="col"><StatCard label="Total bookings" :value="summary.total ?? 0" icon="🎒" variant="primary" /></div>
      <div class="col"><StatCard label="Active" :value="summary.booked ?? 0" icon="⛰️" variant="success" /></div>
      <div class="col"><StatCard label="Completed" :value="summary.completed ?? 0" icon="🏁" variant="info" /></div>
      <div class="col"><StatCard label="Cancelled" :value="summary.cancelled ?? 0" icon="🚫" variant="danger" /></div>
    </div>

    <div class="row g-4">
      <div class="col-lg-6">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h5 mb-0">Recent bookings</h2>
          <RouterLink class="small text-decoration-none" to="/user/bookings">View all →</RouterLink>
        </div>
        <div class="list-group shadow-sm rounded-3">
          <div v-for="b in bookings" :key="b.id" class="list-group-item list-group-item-action">
            <div class="d-flex justify-content-between">
              <div>
                <strong>{{ b.trek_name }}</strong>
                <div class="small text-muted">{{ b.booking_id }} · Starts {{ fmtDate(b.trek_start_date) }} · {{ b.participants }} pax</div>
              </div>
              <span class="badge align-self-center" :class="statusClass(b.status)">{{ b.status }}</span>
            </div>
          </div>
          <div v-if="!bookings.length" class="list-group-item text-muted small">No bookings yet.</div>
        </div>
      </div>

      <div class="col-lg-6">
        <h2 class="h5 mb-2">Recommended upcoming treks</h2>
        <div class="row row-cols-1 row-cols-md-2 g-3">
          <div v-for="t in recommended" :key="t.id" class="col">
            <TrekCard :trek="t" @view="book" @book="book" />
          </div>
          <div v-if="!recommended.length" class="col-12"><div class="alert alert-info mb-0">No open treks right now — check back soon!</div></div>
        </div>
      </div>
    </div>
  </div>
</template>
