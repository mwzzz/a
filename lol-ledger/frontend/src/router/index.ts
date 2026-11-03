import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        { path: '', name: 'overview', component: () => import('@/views/OverviewView.vue') },
        { path: 'batches', name: 'batches', component: () => import('@/views/BatchesView.vue') },
        { path: 'players', name: 'players', component: () => import('@/views/PlayersView.vue') },
        { path: 'records', name: 'records', component: () => import('@/views/RecordsView.vue') },
        { path: 'ledger', name: 'ledger', component: () => import('@/views/LedgerView.vue') },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
        },
        {
          path: 'platform',
          name: 'platform',
          component: () => import('@/views/PlatformView.vue'),
          meta: { requiresSuperadmin: true },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (auth.isLoggedIn && to.name === 'login') {
      return { name: auth.isSuperadmin ? 'platform' : 'overview' }
    }
    return true
  }

  if (!auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.reset()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  // 开发者只管商家与账号，不进入门店业务页面
  if (auth.isSuperadmin && to.name !== 'platform') {
    return { name: 'platform' }
  }

  if (to.meta.requiresSuperadmin && !auth.isSuperadmin) {
    ElMessage.warning('只有开发者账号可以打开这个页面')
    return { name: 'overview' }
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    ElMessage.warning('只有管理员可以打开这个页面')
    return { name: 'overview' }
  }

  return true
})

export default router
