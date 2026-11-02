<script setup>
import { reactive, ref } from 'vue'
import { api, auth } from '../api/client'
import { toastOk, toastErr } from '../store'

const profile = reactive({ full_name: '', email: '', phone: '' })
const passwordForm = reactive({ current_password: '', password: '', confirm_password: '' })
const errors = ref({})
const loading = ref(false)
const staffExtra = reactive({ specialization: '', contact_details: '' })

async function load() {
  try {
    const res = await api.me()
    Object.assign(profile, { full_name: res.data.full_name, email: res.data.email, phone: res.data.phone || '' })
    if (res.data.role === 'staff') {
      staffExtra.specialization = res.data.specialization || ''
      staffExtra.contact_details = res.data.contact_details || ''
    }
  } catch (e) {
    toastErr(e.message)
  }
}
load()

async function saveProfile() {
  loading.value = true
  errors.value = {}
  try {
    const payload = { ...profile }
    if (auth.role === 'staff') Object.assign(payload, staffExtra)
    const res = await api.updateProfile(payload)
    auth.setUser(res.data)
    toastOk('Profile updated successfully')
  } catch (e) {
    errors.value = e.errors || {}
    toastErr(e.message)
  } finally {
    loading.value = false
  }
}

async function changePassword() {
  if (passwordForm.password !== passwordForm.confirm_password) {
    errors.value = { confirm_password: 'Passwords do not match.' }
    return
  }
  try {
    await api.updateProfile({ ...passwordForm })
    Object.assign(passwordForm, { current_password: '', password: '', confirm_password: '' })
    toastOk('Password changed successfully')
  } catch (e) {
    errors.value = e.errors || {}
    toastErr(e.message)
  }
}
</script>

<template>
  <div class="row justify-content-center">
    <div class="col-12 col-lg-8 col-xl-6">
      <h1 class="h4 mb-4">👤 My Profile <span class="badge text-bg-light text-uppercase ms-2">{{ auth.role }}</span></h1>

      <div class="card shadow-sm border-0 rounded-4 mb-4">
        <div class="card-body p-4">
          <h2 class="h6 mb-3">Account details</h2>
          <form novalidate @submit.prevent="saveProfile">
            <div class="row g-3">
              <div class="col-md-6">
                <label class="form-label">Full name</label>
                <input v-model.trim="profile.full_name" class="form-control" required minlength="3" maxlength="120" />
                <div class="small text-danger">{{ errors.full_name }}</div>
              </div>
              <div class="col-md-6">
                <label class="form-label">Email</label>
                <input v-model.trim="profile.email" type="email" class="form-control" required />
                <div class="small text-danger">{{ errors.email }}</div>
              </div>
              <div class="col-md-6">
                <label class="form-label">Phone</label>
                <input v-model.trim="profile.phone" type="tel" class="form-control" minlength="8" maxlength="20" />
                <div class="small text-danger">{{ errors.phone }}</div>
              </div>
              <template v-if="auth.role === 'staff'">
                <div class="col-md-6">
                  <label class="form-label">Specialization</label>
                  <input v-model.trim="staffExtra.specialization" class="form-control" maxlength="80" />
                  <div class="small text-danger">{{ errors.specialization }}</div>
                </div>
                <div class="col-12">
                  <label class="form-label">Contact details</label>
                  <input v-model.trim="staffExtra.contact_details" class="form-control" maxlength="200" />
                </div>
              </template>
            </div>
            <button class="btn btn-success mt-3 px-4" :disabled="loading">Save changes</button>
          </form>
        </div>
      </div>

      <div class="card shadow-sm border-0 rounded-4">
        <div class="card-body p-4">
          <h2 class="h6 mb-3">Change password</h2>
          <form novalidate @submit.prevent="changePassword">
            <div class="row g-3">
              <div class="col-md-4">
                <label class="form-label">Current password</label>
                <input v-model="passwordForm.current_password" type="password" class="form-control" required autocomplete="current-password" />
                <div class="small text-danger">{{ errors.current_password }}</div>
              </div>
              <div class="col-md-4">
                <label class="form-label">New password</label>
                <input v-model="passwordForm.password" type="password" class="form-control" required minlength="8" autocomplete="new-password" />
                <div class="small text-danger">{{ errors.password }}</div>
              </div>
              <div class="col-md-4">
                <label class="form-label">Confirm new password</label>
                <input v-model="passwordForm.confirm_password" type="password" class="form-control" required minlength="8" autocomplete="new-password" />
                <div class="small text-danger">{{ errors.confirm_password }}</div>
              </div>
            </div>
            <button class="btn btn-outline-success mt-3 px-4">Update password</button>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>
