import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import { useZjAuthStore } from '@/stores/zjAuth'

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
      path: '/zj/login',
      name: 'zj-login',
      component: () => import('@/views/zj/ZjLoginView.vue'),
      meta: { public: true, zj: true },
    },
    {
      path: '/zj',
      component: () => import('@/layouts/ZjLayout.vue'),
      meta: { zj: true },
      children: [
        {
          path: '',
          name: 'zj-query',
          component: () => import('@/views/zj/ZjQueryView.vue'),
        },
      ],
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        { path: '', name: 'overview', component: () => import('@/views/OverviewView.vue') },
        { path: 'summary', name: 'summary', component: () => import('@/views/SummaryView.vue') },
        { path: 'batches', redirect: { name: 'summary' } },
        { path: 'players', name: 'players', component: () => import('@/views/PlayersView.vue') },
        {
          path: 'reports',
          name: 'reports',
          component: () => import('@/views/ReportsView.vue'),
        },
        { path: 'records', name: 'records', redirect: { name: 'reports', query: { tab: 'records' } } },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
        },
        {
          path: 'tools',
          name: 'tools',
          component: () => import('@/views/ToolsView.vue'),
        },
        {
          path: 'tools/queue',
          name: 'queue',
          component: () => import('@/views/QueueView.vue'),
        },
        {
          path: 'tools/name-lists',
          name: 'name-lists',
          component: () => import('@/views/NameListView.vue'),
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
  // 查战绩有自己的账号体系，走独立分支，不能落到记账的登录/超管规则里
  if (to.meta.zj) {
    const zjAuth = useZjAuthStore()
    if (to.name === 'zj-login') {
      return zjAuth.isLoggedIn ? { name: 'zj-query' } : true
    }
    if (!zjAuth.isLoggedIn) {
      return { name: 'zj-login', query: { redirect: to.fullPath } }
    }
    if (!zjAuth.user) {
      try {
        await zjAuth.fetchMe()
      } catch {
        zjAuth.clear()
        return { name: 'zj-login', query: { redirect: to.fullPath } }
      }
    }
    return true
  }

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
