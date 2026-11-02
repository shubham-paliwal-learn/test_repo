<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../../api/client'
import { toastOk, toastErr } from '../../store'
import { fmtDate, statusClass, difficultyIcon } from '../../utils/format'
import BookModal from './BookModal.vue'

const route = useRoute()
const router = useRouter()
const trek = ref(null)
const loading = ref(true)
const selectedTrek = ref(null)
const submitting = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await api.trek(route.params.id)
    trek.value = res.data
  } catch (e) {
    toastErr(e.message)
    router.push('/user/treks')
  } finally { loading.value = false }
}
onMounted(load)

function openBook() { selectedTrek.value = trek.value }

async function confirmBooking({ participants, notes }) {
  submitting.value = true
  try {
    const res = await api.bookTrek({ trek_id: trek.value.id, participants, notes })
    toastOk(res.message || 'Booking confirmed!')
    selectedTrek.value = null
    load()
  } catch (e) { toastErr(e.message) } finally { submitting.value = false }
}
</script>

<template>
  <div v-if="loading" class="text-center py-5"><span class="spinner-border text-success"></span></div>
  <div v-else-if="trek">
    <button class="btn btn-sm btn-outline-secondary mb-3" @click="router.back()">← Back</button>
    <div class="row g-4">
      <div class="col-lg-8">
        <div class="card border-0 shadow-sm rounded-4 h-100">
          <div class="card-body p-4">
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
              <h1 class="h3 mb-1">{{ trek.name }}</h1>
              <div class="d-flex gap-2">
                <span class="badge difficulty-badge text-capitalize" :class="trek.difficulty.toLowerCase()">
                  {{ difficultyIcon(trek.difficulty) }} {{ trek.difficulty }}
                </span>
                <span class="badge" :class="statusClass(trek.status)">{{ trek.status }}</span>
              </div>
            </div>
            <p class="text-muted">📍 {{ trek.location }}<span v-if="trek.region"> · {{ trek.region }}</span> · Trek ID {{ trek.trek_id }}</p>
            <p>{{ trek.description }}</p>

            <h2 class="h6 mt-4">Trail information</h2>
            <div class="row row-cols-2 row-cols-md-3 g-3 small">
              <div class="col"><div class="border rounded p-2">⏱ Duration<br /><strong>{{ trek.duration_days }} day(s)</strong></div></div>
              <div class="col"><div class="border rounded p-2">🗓 Start<br /><strong>{{ fmtDate(trek.start_date) }}</strong></div></div>
              <div class="col"><div class="border rounded p-2">🏁 End<br /><strong>{{ fmtDate(trek.end_date) }}</strong></div></div>
              <div class="col"><div class="border rounded p-2">💰 Base price<br /><strong>₹{{ Number(trek.base_price || 0).toLocaleString('en-IN') }}</strong></div></div>
              <div class="col"><div class="border rounded p-2">🔞 Min age<br /><strong>{{ trek.min_age }} yrs</strong></div></div>
              <div class="col"><div class="border rounded p-2">🧑‍🚀 Lead staff<br /><strong>{{ trek.assigned_staff_name || 'Not assigned' }}</strong></div></div>
            </div>

            <template v-if="trek.instructions">
              <h2 class="h6 mt-4">Instructions for trekkers</h2>
              <div class="alert alert-warning small">{{ trek.instructions }}</div>
            </template>
          </div>
        </div>
      </div>

      <div class="col-lg-4">
        <div class="card border-0 shadow-sm rounded-4">
          <div class="card-body p-4">
            <h2 class="h6">Slot availability</h2>
            <div class="display-6 fw-bold text-success mb-1">{{ trek.available_slots }}</div>
            <p class="small text-muted mb-3">of {{ trek.total_slots }} total slots remaining</p>
            <div class="progress slot-bar mb-3">
              <div class="progress-bar bg-success" :style="{ width: `${Math.round(((trek.total_slots - trek.available_slots) / Math.max(trek.total_slots, 1)) * 100)}%` }"></div>
            </div>

            <div v-if="trek.my_booking" class="alert alert-info small mb-3">
              You already have a booking (<strong>{{ trek.my_booking.status }}</strong>) for this trek.
            </div>

            <button
              class="btn btn-success w-100 py-2"
              :disabled="trek.status !== 'Open' || trek.available_slots <= 0 || !!trek.my_booking?.status === true && trek.my_booking.status === 'Booked'"
              @click="openBook"
            >
              {{ trek.status !== 'Open' ? `Booking closed (${trek.status})` : trek.available_slots <= 0 ? 'Sold out' : 'Book this trek' }}
            </button>
            <p class="small text-muted mt-2 mb-0">Bookings are allowed only when the trek is <strong>Open</strong>. Duplicate bookings are blocked.</p>
          </div>
        </div>
      </div>
    </div>

    <BookModal :trek="selectedTrek" :submitting="submitting" @confirm="confirmBooking" @close="selectedTrek = null" />
  </div>
</template>
