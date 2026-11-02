<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api/client'
import { toastErr, toastOk } from '../../store'
import PaginatedTable from '../../components/PaginatedTable.vue'
import { fmtDateTime, statusClass } from '../../utils/format'

// ---- monthly report ----------------------------------------------------------
const month = ref('')          // YYYY-MM or '' for current month
const report = ref(null)       // { period, key, html, summary }
const loadingReport = ref(false)

async function loadReport() {
  loadingReport.value = true
  try {
    const res = await api.monthlyReport(month.value || undefined)
    report.value = res.data
  } catch (e) {
    toastErr(e.message)
  } finally {
    loadingReport.value = false
  }
}

function printReport() {
  if (!report.value?.html) return
  const w = window.open('', '_blank', 'width=900,height=700')
  w.document.write(`<html><head><title>Monthly Report ${report.value.period}</title>
    <style>body{font-family:system-ui,Arial;padding:24px;color:#212529} table{border-collapse:collapse;width:100%}
    th,td{border:1px solid #dee2e6;padding:6px 10px;text-align:left} h1,h2,h3{color:#1f6f43}</style>
    </head><body>${report.value.html}</body></html>`)
  w.document.close()
  w.focus()
  w.print()
}

// ---- celery jobs ---------------------------------------------------------------
const jobs = ref([])
const pagination = ref(null)
const loadingJobs = ref(false)
const triggering = ref('')

async function loadJobs() {
  loadingJobs.value = true
  try {
    const res = await api.jobRuns()
    jobs.value = res.data.items
    pagination.value = res.data.pagination
  } catch (e) {
    toastErr(e.message)
  } finally {
    loadingJobs.value = false
  }
}

async function trigger(name) {
  triggering.value = name
  try {
    const res = await api.triggerJob(name)
    toastOk(res.message)
    setTimeout(loadJobs, 1500)
  } catch (e) {
    toastErr(e.message)
  } finally {
    triggering.value = ''
  }
}

async function clearCache() {
  if (!confirm('Clear all cached dashboards / trek listings?')) return
  try {
    const res = await api.clearCache()
    toastOk(`${res.message} (backend: ${res.data.backend})`)
  } catch (e) { toastErr(e.message) }
}

function onPage(page) {
  api.jobRuns({ page }).then((res) => {
    jobs.value = res.data.items
    pagination.value = res.data.pagination
  }).catch((e) => toastErr(e.message))
}

onMounted(() => {
  loadReport()
  loadJobs()
})
</script>

<template>
  <div class="mb-3">
    <h1 class="h4 mb-0">Reports &amp; Background Jobs</h1>
    <p class="small text-muted mb-0">Celery scheduled tasks · Redis cache control · job history.</p>
  </div>

  <div class="row g-3">
    <!-- left: monthly report -->
    <div class="col-12 col-xl-8">
      <div class="card border-0 shadow-sm rounded-4 mb-3">
        <div class="card-header bg-white d-flex flex-wrap justify-content-between align-items-center gap-2">
          <span class="fw-semibold">📊 Monthly Activity Report</span>
          <div class="d-flex gap-2">
            <input v-model="month" type="month" class="form-control form-control-sm" style="width:auto" />
            <button class="btn btn-sm btn-outline-success" :disabled="loadingReport" @click="loadReport">Generate</button>
            <button class="btn btn-sm btn-success" :disabled="!report" @click="printReport">🖨 Print</button>
          </div>
        </div>
        <div class="card-body">
          <div v-if="loadingReport" class="text-center py-4"><span class="spinner-border text-success"></span></div>
          <template v-else-if="report">
            <h6 class="text-muted small mb-3">Period: {{ report.period }}</h6>
            <div class="row g-2 mb-3">
              <div v-for="(v, k) in report.summary" :key="k" class="col-6 col-md-3">
                <div class="border rounded-3 p-2 text-center">
                  <div class="fw-bold">{{ typeof v === 'number' ? v.toLocaleString() : v }}</div>
                  <div class="small text-muted text-capitalize">{{ String(k).replaceAll('_', ' ') }}</div>
                </div>
              </div>
            </div>
            <div class="border rounded-3 p-3" style="max-height: 480px; overflow-y: auto" v-html="report.html"></div>
          </template>
        </div>
      </div>
    </div>

    <!-- right: jobs + cache -->
    <div class="col-12 col-xl-4">
      <div class="card border-0 shadow-sm rounded-4 mb-3">
        <div class="card-header bg-white fw-semibold">⚙️ Celery scheduled jobs</div>
        <div class="card-body d-grid gap-2">
          <button class="btn btn-outline-success" :disabled="triggering === 'daily-reminders'" @click="trigger('daily-reminders')">
            <span v-if="triggering === 'daily-reminders'" class="spinner-border spinner-border-sm me-1"></span>
            🗓 Run “Daily departure reminders” now
          </button>
          <button class="btn btn-outline-success" :disabled="triggering === 'monthly-report'" @click="trigger('monthly-report')">
            <span v-if="triggering === 'monthly-report'" class="spinner-border spinner-border-sm me-1"></span>
            📧 Run “Monthly report e-mail” now
          </button>
          <button class="btn btn-outline-danger" @click="clearCache">🧹 Clear application cache</button>
          <p class="small text-muted mb-0">
            Jobs run on the Celery worker when available and fall back to inline execution otherwise.
            Beat schedules them automatically (daily reminders + monthly report).
          </p>
        </div>
      </div>

      <div class="card border-0 shadow-sm rounded-4">
        <div class="card-header bg-white d-flex justify-content-between align-items-center">
          <span class="fw-semibold">🕘 Job run history</span>
          <button class="btn btn-sm btn-outline-secondary" @click="loadJobs">↻</button>
        </div>
        <ul class="list-group list-group-flush" style="max-height: 380px; overflow-y: auto">
          <li v-for="j in jobs" :key="j.id" class="list-group-item small">
            <div class="d-flex justify-content-between">
              <strong>{{ j.job_name }}</strong>
              <span class="badge" :class="statusClass(j.status === 'success' ? 'Active' : j.status === 'failed' ? 'Blacklisted' : 'Pending')">
                {{ j.status }}
              </span>
            </div>
            <div class="text-muted">{{ fmtDateTime(j.started_at) }} → {{ j.finished_at ? fmtDateTime(j.finished_at) : '…' }}</div>
            <div v-if="j.detail" class="fst-italic">{{ j.detail }}</div>
          </li>
          <li v-if="!jobs.length" class="list-group-item text-muted">No job runs recorded yet.</li>
        </ul>
        <PaginatedTable :pagination="pagination" @update="onPage" />
      </div>
    </div>
  </div>
</template>
