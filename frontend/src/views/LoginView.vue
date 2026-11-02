<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from '../api/client'
import { toastErr } from '../store'
import { homeRoute } from '../router'

const router = useRouter()
const route = useRoute()

const form = reactive({ username: '', password: '', role: '' })
const errors = ref({})
const loading = ref(false)

async function submit() {
  loading.value = true
  errors.value = {}
  try {
    const res = await api.login({ ...form })
    auth.setSession(res.data)
    router.push(route.query.next || homeRoute())
  } catch (e) {
    errors.value = e.errors || {}
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="row justify-content-center g-4 align-items-center">
    <div class="col-lg-5 d-none d-lg-block">
      <div class="auth-hero p-5 h-100 d-flex flex-column justify-content-center">
        <h1 class="display-6 fw-bold">⛰️ Trekking Management Application</h1>
        <p class="lead mt-3">Plan, approve and book treks — routes, staff assignments, slot management and bookings in one place.</p>
        <ul class="list-unstyled mt-4 small">
          <li>✅ Role-based dashboards for Admin, Staff and Trekkers</li>
          <li>✅ Real-time slot availability with overbooking protection</li>
          <li>✅ Redis-cached trek listings & Celery background jobs</li>
        </ul>
      </div>
    </div>

    <div class="col-12 col-md-8 col-lg-5 col-xl-4">
      <div class="card shadow-sm border-0 rounded-4">
        <div class="card-body p-4">
          <h2 class="h4 mb-1">Sign in</h2>
          <p class="text-muted small mb-4">Admins and staff log in here; trekkers can <RouterLink to="/register">create an account</RouterLink>.</p>

          <form novalidate @submit.prevent="submit">
            <div class="mb-3">
              <label class="form-label">Username or email</label>
              <input v-model.trim="form.username" class="form-control" required minlength="3" autocomplete="username" />
              <div class="invalid-feedback d-block">{{ errors.username }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label">Password</label>
              <input v-model="form.password" type="password" class="form-control" required minlength="6" autocomplete="current-password" />
              <div class="invalid-feedback d-block">{{ errors.password }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label">Login as <span class="text-muted">(optional)</span></label>
              <select v-model="form.role" class="form-select">
                <option value="">Any role</option>
                <option value="admin">Admin</option>
                <option value="staff">Trek Staff</option>
                <option value="user">Trekker</option>
              </select>
              <div class="invalid-feedback d-block">{{ errors.role }}</div>
            </div>
            <button class="btn btn-success w-100 py-2" :disabled="loading">
              <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Sign in
            </button>
          </form>

          <div class="d-flex justify-content-between mt-3 small">
            <RouterLink to="/register" class="text-decoration-none">New trekker? Register</RouterLink>
            <span class="text-muted">Demo: admin / staff.arun / trek.ravi</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
