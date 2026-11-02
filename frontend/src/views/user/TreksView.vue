<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../api/client'
import { toastOk, toastErr } from '../../store'
import TrekCard from '../../components/TrekCard.vue'
import PaginatedTable from '../../components/PaginatedTable.vue'
import BookModal from './BookModal.vue'

const router = useRouter()
const treks = ref([])
const pagination = ref(null)
const filters = reactive({ search: '', difficulty: '', location: '', status: '', min_duration: '', max_duration: '', only_available: false, sort_by: 'start_date', order: 'asc', page: 1 })
const options = ref({ difficulties: [], locations: [], durations: [] })
const loading = ref(false)
const selectedTrek = ref(null)
const submitting = ref(false)

async function load() {
  loading.value = true
  try {
    const params = { ...filters, only_available: filters.only_available ? 1 : undefined }
    delete params.page
    const res = await api.treks({ ...params, page: filters.page })
    treks.value = res.data.items
    pagination.value = res.data.pagination
  } catch (e) { toastErr(e.message) } finally { loading.value = false }
}

async function loadOptions() {
  try {
    const res = await api.trekFilters()
    options.value = res.data
  } catch { /* non-critical */ }
}

onMounted(() => { loadOptions(); load() })

function applyFilters() { filters.page = 1; load() }
function resetFilters() {
  Object.assign(filters, { search: '', difficulty: '', location: '', status: '', min_duration: '', max_duration: '', only_available: false, sort_by: 'start_date', order: 'asc', page: 1 })
  load()
}
function changePage(page) { filters.page = page; load() }

function openDetail(trek) { router.push(`/user/treks/${trek.id}`) }
function openBook(trek) { selectedTrek.value = trek }

async function confirmBooking({ participants, notes }) {
  submitting.value = true
  try {
    const res = await api.bookTrek({ trek_id: selectedTrek.value.id, participants, notes })
    toastOk(res.message || 'Booking confirmed!')
    selectedTrek.value = null
    load()
  } catch (e) { toastErr(e.message) } finally { submitting.value = false }
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <h1 class="h4 mb-0">🥾 Explore Treks</h1>
      <span class="badge text-bg-light">Cache: {{ treks.length ? 'Redis / in-memory' : '-' }}</span>
    </div>

    <!-- search & filter bar -->
    <div class="card border-0 shadow-sm rounded-4 mb-4">
      <div class="card-body py-3">
        <form class="row g-2 align-items-end" @submit.prevent="applyFilters">
          <div class="col-12 col-md-3">
            <label class="form-label small mb-1">Search</label>
            <input v-model.trim="filters.search" class="form-control form-control-sm" placeholder="Name, place, region…" />
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small mb-1">Difficulty</label>
            <select v-model="filters.difficulty" class="form-select form-select-sm">
              <option value="">All</option>
              <option v-for="d in options.difficulties" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small mb-1">Location</label>
            <select v-model="filters.location" class="form-select form-select-sm">
              <option value="">All</option>
              <option v-for="l in options.locations" :key="l" :value="l">{{ l }}</option>
            </select>
          </div>
          <div class="col-6 col-md-2">
            <label class="form-label small mb-1">Duration (days)</label>
            <div class="input-group input-group-sm">
              <input v-model.number="filters.min_duration" type="number" min="1" class="form-control" placeholder="min" />
              <input v-model.number="filters.max_duration" type="number" min="1" class="form-control" placeholder="max" />
            </div>
          </div>
          <div class="col-6 col-md-1 d-flex align-items-center">
            <div class="form-check">
              <input id="avail" v-model="filters.only_available" class="form-check-input" type="checkbox" />
              <label class="form-check-label small" for="avail">Slots left</label>
            </div>
          </div>
          <div class="col-12 col-md-2 d-flex gap-2">
            <button class="btn btn-sm btn-success flex-grow-1">Apply</button>
            <button type="button" class="btn btn-sm btn-outline-secondary" @click="resetFilters">Reset</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="loading" class="text-center py-5"><span class="spinner-border text-success"></span></div>
    <div v-else-if="!treks.length" class="alert alert-info">No treks match your filters. Try widening the search.</div>

    <div v-else class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 row-cols-xxl-4 g-4">
      <div v-for="t in treks" :key="t.id" class="col">
        <TrekCard :trek="t" @view="openDetail" @book="openBook" />
      </div>
    </div>

    <PaginatedTable :pagination="pagination" @update="changePage" />

    <BookModal :trek="selectedTrek" :submitting="submitting" @confirm="confirmBooking" @close="selectedTrek = null" />
  </div>
</template>
