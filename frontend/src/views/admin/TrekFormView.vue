<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../../api/client'
import { toastErr, toastOk } from '../../store'

const route = useRoute()
const router = useRouter()

const trekId = computed(() => route.params.id)
const isEdit = computed(() => !!trekId.value && trekId.value !== 'new')

const staffOptions = ref([])
const saving = ref(false)
const loading = ref(false)
const fieldErrors = ref({})
const serverMessage = ref('')

const form = reactive({
  name: '',
  location: '',
  region: '',
  difficulty: 'Moderate',
  duration_days: 3,
  total_slots: 20,
  start_date: '',
  end_date: '',
  base_price: 5000,
  min_age: 12,
  status: 'Pending',
  assigned_staff_id: '',
  description: '',
  instructions: '',
})

// ---- derived validation (HTML5 + JS) ----------------------------------------
const dateError = computed(() => {
  if (!form.start_date) return 'Start date is required.'
  if (form.end_date && form.end_date < form.start_date) return 'End date cannot be before the start date.'
  return ''
})

const expectedSpan = computed(() => {
  if (!form.start_date || !form.end_date) return null
  const s = new Date(form.start_date)
  const e = new Date(form.end_date)
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return null
  return Math.round((e - s) / 86400000) + 1
})

const durationError = computed(() => {
  if (expectedSpan.value && Number(form.duration_days) !== expectedSpan.value) {
    return `Duration should be ${expectedSpan.value} day(s) for the selected dates.`
  }
  return ''
})

const formValid = computed(() => !dateError.value && !durationError.value)

async function autoFillDuration() {
  if (expectedSpan.value) form.duration_days = expectedSpan.value
}

async function loadStaff() {
  try {
    const res = await api.adminStaff({ per_page: 100 })
    staffOptions.value = res.data.items.filter((s) => s.status === 'Active')
  } catch { /* optional */ }
}

async function loadTrek() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const res = await api.trek(trekId.value, { all: 1 })
    const t = res.data
    Object.assign(form, {
      name: t.name,
      location: t.location,
      region: t.region || '',
      difficulty: t.difficulty,
      duration_days: t.duration_days,
      total_slots: t.total_slots,
      start_date: t.start_date || '',
      end_date: t.end_date || '',
      base_price: t.base_price,
      min_age: t.min_age ?? 12,
      status: t.status,
      assigned_staff_id: t.assigned_staff_id ? String(t.assigned_staff_id) : '',
      description: t.description || '',
      instructions: t.instructions || '',
    })
  } catch (e) {
    toastErr(e.message)
    router.push('/admin/treks')
  } finally {
    loading.value = false
  }
}

async function submit() {
  fieldErrors.value = {}
  serverMessage.value = ''
  if (!formValid.value) {
    toastErr('Please fix the highlighted fields before saving.')
    return
  }
  saving.value = true
  const payload = {
    ...form,
    duration_days: Number(form.duration_days),
    total_slots: Number(form.total_slots),
    base_price: Number(form.base_price),
    min_age: Number(form.min_age),
    assigned_staff_id: form.assigned_staff_id ? Number(form.assigned_staff_id) : null,
  }
  try {
    if (isEdit.value) {
      await api.updateTrek(trekId.value, payload)
      toastOk('Trek updated successfully')
    } else {
      await api.createTrek(payload)
      toastOk('Trek created successfully')
    }
    router.push('/admin/treks')
  } catch (e) {
    serverMessage.value = e.message
    fieldErrors.value = e.errors || {}
    toastErr(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadStaff()
  await loadTrek()
})
</script>

<template>
  <div v-if="loading" class="text-center py-5"><span class="spinner-border text-success"></span></div>
  <div v-else class="row justify-content-center">
    <div class="col-12 col-lg-9 col-xl-8">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h4 mb-0">{{ isEdit ? `Edit Trek #${trekId}` : 'Create New Trek' }}</h1>
        <RouterLink class="btn btn-sm btn-outline-secondary" to="/admin/treks">← Back to list</RouterLink>
      </div>

      <div v-if="serverMessage" class="alert alert-danger py-2 small">{{ serverMessage }}</div>

      <form @submit.prevent="submit" novalidate>
        <div class="card border-0 shadow-sm rounded-4 mb-3">
          <div class="card-header bg-white fw-semibold">Route details</div>
          <div class="card-body row g-3">
            <div class="col-12 col-md-6">
              <label class="form-label small">Trek name *</label>
              <input v-model.trim="form.name" class="form-control" :class="{ 'is-invalid': fieldErrors.name }"
                     required minlength="4" maxlength="120" placeholder="e.g. Hampta Pass Trek" />
              <div class="invalid-feedback d-block">{{ fieldErrors.name }}</div>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Location *</label>
              <input v-model.trim="form.location" class="form-control" :class="{ 'is-invalid': fieldErrors.location }"
                     required minlength="3" maxlength="120" placeholder="e.g. Manali, HP" />
              <div class="invalid-feedback d-block">{{ fieldErrors.location }}</div>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Region</label>
              <input v-model.trim="form.region" class="form-control" maxlength="80" placeholder="e.g. Himachal Pradesh" />
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Difficulty *</label>
              <select v-model="form.difficulty" class="form-select" required>
                <option>Easy</option><option>Moderate</option><option>Hard</option>
              </select>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Duration (days) *</label>
              <input v-model.number="form.duration_days" type="number" min="1" max="90" class="form-control"
                     :class="{ 'is-invalid': durationError || fieldErrors.duration_days }" required />
              <div class="invalid-feedback d-block">{{ durationError || fieldErrors.duration_days }}</div>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Total slots *</label>
              <input v-model.number="form.total_slots" type="number" min="1" max="500" class="form-control"
                     :class="{ 'is-invalid': fieldErrors.total_slots }" required />
              <div class="invalid-feedback d-block">{{ fieldErrors.total_slots }}</div>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Base price (₹)</label>
              <input v-model.number="form.base_price" type="number" min="0" step="50" class="form-control" />
            </div>
          </div>
        </div>

        <div class="card border-0 shadow-sm rounded-4 mb-3">
          <div class="card-header bg-white fw-semibold">Schedule &amp; staffing</div>
          <div class="card-body row g-3">
            <div class="col-6 col-md-3">
              <label class="form-label small">Start date *</label>
              <input v-model="form.start_date" type="date" class="form-control"
                     :class="{ 'is-invalid': dateError || fieldErrors.start_date }" required @change="autoFillDuration" />
              <div class="invalid-feedback d-block">{{ dateError || fieldErrors.start_date }}</div>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">End date</label>
              <input v-model="form.end_date" type="date" class="form-control"
                     :class="{ 'is-invalid': dateError || fieldErrors.end_date }" :min="form.start_date" @change="autoFillDuration" />
              <div class="invalid-feedback d-block">{{ dateError || fieldErrors.end_date }}</div>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Status *</label>
              <select v-model="form.status" class="form-select" required>
                <option>Pending</option><option>Approved</option><option>Open</option>
                <option>Closed</option><option>Completed</option>
              </select>
              <div class="form-text">Open treks require an assigned staff member.</div>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Assigned staff</label>
              <select v-model="form.assigned_staff_id" class="form-select">
                <option value="">— Unassigned —</option>
                <option v-for="s in staffOptions" :key="s.id" :value="String(s.id)">{{ s.full_name }}</option>
              </select>
            </div>
            <div class="col-6 col-md-3">
              <label class="form-label small">Minimum age</label>
              <input v-model.number="form.min_age" type="number" min="5" max="100" class="form-control" />
            </div>
          </div>
        </div>

        <div class="card border-0 shadow-sm rounded-4 mb-3">
          <div class="card-header bg-white fw-semibold">Description &amp; instructions</div>
          <div class="card-body row g-3">
            <div class="col-12">
              <label class="form-label small">Description</label>
              <textarea v-model="form.description" rows="3" maxlength="2000" class="form-control"
                        placeholder="What makes this trek special…"></textarea>
            </div>
            <div class="col-12">
              <label class="form-label small">Participant instructions</label>
              <textarea v-model="form.instructions" rows="3" maxlength="2000" class="form-control"
                        placeholder="Gear list, fitness prep, meeting point…"></textarea>
            </div>
          </div>
        </div>

        <div class="d-flex gap-2 justify-content-end">
          <RouterLink class="btn btn-outline-secondary" to="/admin/treks">Cancel</RouterLink>
          <button class="btn btn-success" type="submit" :disabled="saving">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>
            {{ isEdit ? 'Save changes' : 'Create trek' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
