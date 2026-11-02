<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, auth } from '../api/client'
import { toastErr } from '../store'

const router = useRouter()
const form = reactive({ full_name: '', username: '', email: '', phone: '', password: '', confirm_password: '' })
const errors = ref({})
const loading = ref(false)

async function submit() {
  if (form.password !== form.confirm_password) {
    errors.value = { confirm_password: 'Passwords do not match.' }
    return
  }
  loading.value = true
  errors.value = {}
  try {
    const res = await api.register({ ...form })
    auth.setSession(res.data)
    router.push('/user')
  } catch (e) {
    errors.value = e.errors || {}
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="row justify-content-center">
    <div class="col-12 col-md-8 col-lg-6 col-xl-5">
      <div class="card shadow-sm border-0 rounded-4">
        <div class="card-body p-4">
          <h2 class="h4 mb-1">Create your trekker account</h2>
          <p class="text-muted small mb-4">Only trekkers can self-register. Admin and staff accounts are created by the administrator.</p>

          <form novalidate @submit.prevent="submit">
            <div class="row g-3">
              <div class="col-md-6">
                <label class="form-label">Full name</label>
                <input v-model.trim="form.full_name" class="form-control" required minlength="3" maxlength="120" />
                <div class="d-block small text-danger">{{ errors.full_name }}</div>
              </div>
              <div class="col-md-6">
                <label class="form-label">Username</label>
                <input v-model.trim="form.username" class="form-control" required minlength="3" maxlength="64" pattern="[A-Za-z0-9._]+" />
                <div class="d-block small text-danger">{{ errors.username }}</div>
              </div>
              <div class="col-md-6">
                <label class="form-label">Email</label>
                <input v-model.trim="form.email" type="email" class="form-control" required />
                <div class="d-block small text-danger">{{ errors.email }}</div>
              </div>
              <div class="col-md-6">
                <label class="form-label">Phone <span class="text-muted">(optional)</span></label>
                <input v-model.trim="form.phone" type="tel" class="form-control" minlength="8" maxlength="20" pattern="[+0-9\-\s()]+" />
                <div class="d-block small text-danger">{{ errors.phone }}</div>
              </div>
              <div class="col-md-6">
                <label class="form-label">Password</label>
                <input v-model="form.password" type="password" class="form-control" required minlength="8" autocomplete="new-password" />
                <div class="d-block small text-danger">{{ errors.password }}</div>
                <div class="form-text">Minimum 8 characters.</div>
              </div>
              <div class="col-md-6">
                <label class="form-label">Confirm password</label>
                <input v-model="form.confirm_password" type="password" class="form-control" required minlength="8" autocomplete="new-password" />
                <div class="d-block small text-danger">{{ errors.confirm_password }}</div>
              </div>
            </div>
            <button class="btn btn-success w-100 py-2 mt-3" :disabled="loading">
              <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Register
            </button>
          </form>

          <p class="text-center small mt-3 mb-0">Already registered? <RouterLink to="/login">Sign in</RouterLink></p>
        </div>
      </div>
    </div>
  </div>
</template>
