import { createRouter, createWebHashHistory } from 'vue-router'
import { auth } from '../api/client'

const routes = [
  { path: '/', redirect: () => homeRoute() },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { public: true } },

  // ---- Trekker ----
  { path: '/user', name: 'user-dashboard', component: () => import('../views/user/DashboardView.vue'), meta: { roles: ['user'] } },
  { path: '/user/treks', name: 'user-treks', component: () => import('../views/user/TreksView.vue'), meta: { roles: ['user'] } },
  { path: '/user/treks/:id', name: 'user-trek-detail', component: () => import('../views/user/TrekDetailView.vue'), meta: { roles: ['user'] } },
  { path: '/user/bookings', name: 'user-bookings', component: () => import('../views/user/BookingsView.vue'), meta: { roles: ['user'] } },
  { path: '/user/profile', name: 'user-profile', component: () => import('../views/ProfileView.vue'), meta: { roles: ['user', 'staff', 'admin'] } },

  // ---- Staff ----
  { path: '/staff', name: 'staff-dashboard', component: () => import('../views/staff/DashboardView.vue'), meta: { roles: ['staff'] } },
  { path: '/staff/treks/:id', name: 'staff-trek', component: () => import('../views/staff/TrekManageView.vue'), meta: { roles: ['staff'] } },

  // ---- Admin ----
  { path: '/admin', name: 'admin-dashboard', component: () => import('../views/admin/DashboardView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/treks', name: 'admin-treks', component: () => import('../views/admin/TreksView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/treks/new', name: 'admin-trek-new', component: () => import('../views/admin/TrekFormView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/treks/:id/edit', name: 'admin-trek-edit', component: () => import('../views/admin/TrekFormView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/staff', name: 'admin-staff', component: () => import('../views/admin/StaffView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/users', name: 'admin-users', component: () => import('../views/admin/UsersView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/bookings', name: 'admin-bookings', component: () => import('../views/admin/BookingsView.vue'), meta: { roles: ['admin'] } },
  { path: '/admin/reports', name: 'admin-reports', component: () => import('../views/admin/ReportsView.vue'), meta: { roles: ['admin'] } },

  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('../views/NotFoundView.vue'), meta: { public: true } },
]

export function homeRoute() {
  if (!auth.isAuthenticated) return '/login'
  return { admin: '/admin', staff: '/staff', user: '/user' }[auth.role] || '/login'
}

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  if (to.meta.public) {
    // authenticated users should not sit on login/register
    if (auth.isAuthenticated && ['/login', '/register'].includes(to.path)) return homeRoute()
    return true
  }
  if (!auth.isAuthenticated) return { path: '/login', query: { next: to.fullPath } }
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) return homeRoute()
  return true
})

export default router
