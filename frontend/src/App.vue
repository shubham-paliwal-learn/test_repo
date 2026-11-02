<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, auth } from './api/client'
import { toasts, removeToast, ui, markAllRead, deleteNotification } from './store'
import { homeRoute } from './router'

const router = useRouter()

// ---- global search (admin only) -------------------------------------------
const searchTerm = ref('')
let searchTimer = null

function onSearchInput() {
  clearTimeout(searchTimer)
  if (auth.role !== 'admin') return
  if (searchTerm.value.trim().length < 2) {
    ui.searchResults = null
    return
  }
  searchTimer = setTimeout(async () => {
    ui.searching = true
    try {
      const res = await api.adminSearch(searchTerm.value.trim())
      ui.searchResults = res.data
    } catch {
      ui.searchResults = null
    } finally {
      ui.searching = false
    }
  }, 300)
}

function gotoResult(kind, id) {
  ui.searchResults = null
  searchTerm.value = ''
  const routes = { trek: `/admin/treks/${id}/edit`, user: '/admin/users', staff: '/admin/staff' }
  router.push(routes[kind] || '/admin')
}

// ---- notifications ----------------------------------------------------------
const showNotifs = ref(false)

async function logout() {
  try { await api.logout() } catch { /* token is client-side anyway */ }
  auth.clear()
  ui.notifications = []
  ui.unread = 0
  router.push('/login')
}

onMounted(() => {
  // keep the bell fresh when navigating between views
})
</script>

<template>
  <div class="min-vh-100 d-flex flex-column">
    <nav class="navbar navbar-expand-lg navbar-dark tma-navbar sticky-top shadow-sm">
      <div class="container-fluid px-3">
        <RouterLink class="navbar-brand fw-bold" :to="homeRoute()">
          <span class="brand-icon">⛰️</span> TMA
        </RouterLink>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav">
          <span class="navbar-toggler-icon"></span>
        </button>

        <div class="collapse navbar-collapse" id="mainNav">
          <!-- role based menu -->
          <ul v-if="auth.isAuthenticated" class="navbar-nav me-auto mb-2 mb-lg-0">
            <template v-if="auth.role === 'user'">
              <li class="nav-item"><RouterLink class="nav-link" to="/user">Dashboard</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/user/treks">Explore Treks</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/user/bookings">My Bookings</RouterLink></li>
            </template>
            <template v-else-if="auth.role === 'staff'">
              <li class="nav-item"><RouterLink class="nav-link" to="/staff">Dashboard</RouterLink></li>
            </template>
            <template v-else-if="auth.role === 'admin'">
              <li class="nav-item"><RouterLink class="nav-link" to="/admin">Dashboard</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/admin/treks">Treks</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/admin/staff">Staff</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/admin/users">Users</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/admin/bookings">Bookings</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/admin/reports">Reports & Jobs</RouterLink></li>
            </template>
            <li class="nav-item"><RouterLink class="nav-link" to="/user/profile">Profile</RouterLink></li>
          </ul>

          <!-- admin global search -->
          <div v-if="auth.role === 'admin'" class="position-relative me-lg-3 my-2 my-lg-0" style="min-width: 240px">
            <input
              v-model="searchTerm"
              class="form-control form-control-sm"
              type="search"
              placeholder="Search users / staff / treks…"
              @input="onSearchInput"
            />
            <div v-if="ui.searchResults" class="card position-absolute w-100 shadow border-0" style="z-index: 1050; top: 110%">
              <ul class="list-group list-group-flush small">
                <li v-for="t in ui.searchResults.treks" :key="`t${t.id}`" class="list-group-item cursor-pointer" @click="gotoResult('trek', t.id)">
                  ⛰️ {{ t.name }} <span class="text-muted">– {{ t.location }}</span>
                </li>
                <li v-for="u in ui.searchResults.users" :key="`u${u.id}`" class="list-group-item cursor-pointer" @click="gotoResult('user')">
                  👤 {{ u.full_name }} <span class="text-muted">({{ u.email }})</span>
                </li>
                <li v-for="s in ui.searchResults.staff" :key="`s${s.id}`" class="list-group-item cursor-pointer" @click="gotoResult('staff')">
                  🧑‍🚀 {{ s.full_name }} <span class="text-muted">({{ s.specialization }})</span>
                </li>
                <li v-if="!ui.searchResults.treks.length && !ui.searchResults.users.length && !ui.searchResults.staff.length"
                    class="list-group-item text-muted">No matches found.</li>
              </ul>
            </div>
          </div>

          <ul class="navbar-nav ms-auto align-items-lg-center">
            <!-- notification bell -->
            <li v-if="auth.isAuthenticated" class="nav-item position-relative me-lg-2">
              <button class="btn btn-sm btn-outline-light position-relative" @click="showNotifs = !showNotifs">
                🔔
                <span v-if="ui.unread" class="notif-dot"></span>
              </button>
              <div v-if="showNotifs" class="card shadow border-0 position-absolute end-0 mt-2" style="width: 320px; z-index: 1060">
                <div class="card-header d-flex justify-content-between align-items-center py-2">
                  <strong class="small">Notifications</strong>
                  <div>
                    <button class="btn btn-link btn-sm p-0 me-2" @click="markAllRead()">Mark all read</button>
                    <button class="btn-close btn-sm" @click="showNotifs = false"></button>
                  </div>
                </div>
                <ul class="list-group list-group-flush" style="max-height: 320px; overflow-y: auto">
                  <li v-for="n in ui.notifications" :key="n.id" class="list-group-item d-flex justify-content-between gap-2 small">
                    <div>
                      <strong>{{ n.title }}</strong>
                      <div class="text-muted">{{ n.message }}</div>
                      <div class="text-muted fst-italic">{{ new Date(n.created_at + 'Z').toLocaleString() }}</div>
                    </div>
                    <button class="btn btn-link btn-sm text-danger p-0 align-self-start" @click="deleteNotification(n.id)">✕</button>
                  </li>
                  <li v-if="!ui.notifications.length" class="list-group-item text-muted small">You're all caught up 🎉</li>
                </ul>
              </div>
            </li>

            <li v-if="auth.isAuthenticated" class="nav-item dropdown">
              <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">
                {{ auth.user?.full_name || 'Account' }}
                <span class="badge text-bg-light text-uppercase ms-1">{{ auth.role }}</span>
              </a>
              <ul class="dropdown-menu dropdown-menu-end">
                <li><RouterLink class="dropdown-item" to="/user/profile">My profile</RouterLink></li>
                <li><hr class="dropdown-divider" /></li>
                <li><a class="dropdown-item text-danger" href="#" @click.prevent="logout">Log out</a></li>
              </ul>
            </li>
            <template v-else>
              <li class="nav-item"><RouterLink class="nav-link" to="/login">Login</RouterLink></li>
              <li class="nav-item"><RouterLink class="nav-link" to="/register">Register</RouterLink></li>
            </template>
          </ul>
        </div>
      </div>
    </nav>

    <main class="flex-grow-1">
      <div class="container-fluid px-3 py-4">
        <RouterView />
      </div>
    </main>

    <footer class="app-footer text-center py-3 border-top bg-white">
      Trekking Management Application · Flask API + VueJS UI + Redis cache + Celery jobs
    </footer>

    <!-- toast stack -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1090">
      <div v-for="t in toasts.items" :key="t.id" class="toast align-items-center border-0 show" :class="`text-bg-${t.variant}`" role="alert">
        <div class="d-flex">
          <div class="toast-body">{{ t.message }}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" @click="removeToast(t.id)"></button>
        </div>
      </div>
    </div>
  </div>
</template>
