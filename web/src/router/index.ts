import { createRouter, createWebHistory, type Router, type RouterHistory, type RouteRecordRaw } from 'vue-router'

import { hasAuthToken } from '@/utils/authStorage'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: {
      title: '登录',
      guestOnly: true
    }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    meta: {
      title: '工作台',
      requiresAuth: true
    },
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
        meta: {
          title: '首页',
          requiresAuth: true
        }
      },
      {
        path: 'folders/:pathId?',
        name: 'folder',
        component: () => import('@/views/files/FolderView.vue'),
        meta: {
          title: '目录',
          requiresAuth: true
        }
      },
      {
        path: 'file/:fileId',
        name: 'file-detail',
        component: () => import('@/views/files/FileDetailView.vue'),
        meta: {
          title: '文件详情',
          requiresAuth: true
        }
      },
      {
        path: 'markdown/:fileId?',
        name: 'markdown',
        component: () => import('@/views/markdown/MarkdownView.vue'),
        meta: {
          title: '文件详情跳转',
          requiresAuth: true
        }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/settings/SettingsView.vue'),
        meta: {
          title: '系统配置',
          requiresAuth: true
        }
      },
      {
        path: 'search',
        name: 'search',
        component: () => import('@/views/search/SearchView.vue'),
        meta: {
          title: '搜索',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

export function createAppRouter(history: RouterHistory = createWebHistory()) {
  return createRouter({
    history,
    routes
  })
}

export function installRouteGuards(router: Router) {
  router.beforeEach((to) => {
    const isAuthenticated = hasAuthToken()

    if (to.meta.requiresAuth && !isAuthenticated) {
      return {
        name: 'login',
        query: {
          redirect: to.fullPath
        }
      }
    }

    if (to.meta.guestOnly && isAuthenticated) {
      return { name: 'dashboard' }
    }

    return true
  })

  router.afterEach((to) => {
    document.title = `${to.meta.title} - PFMT`
  })
}

const router = createAppRouter()
installRouteGuards(router)

export default router
