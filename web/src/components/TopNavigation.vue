<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Fold,
  FolderOpened,
  HomeFilled,
  Setting,
  SwitchButton,
  UploadFilled,
  Search
} from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/authStore'
import { useSettingsStore } from '@/stores/settingsStore'

defineProps<{
  sidebarCollapsed: boolean
}>()

const emit = defineEmits<{
  toggleSidebar: []
}>()

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const searchKeyword = ref('')

const pageTitle = computed(() => route.meta.title ?? '工作台')
const displayName = computed(() => authStore.user?.display_name ?? authStore.user?.username ?? '单用户')

function navigate(name: string) {
  void router.push({ name })
}

function openRootFolder() {
  void router.push({
    name: 'folder',
    params: {
      pathId: 'root'
    }
  })
}

async function handleLogout() {
  await authStore.logout()
  await router.push({ name: 'login' })
}

function submitSearch() {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    return
  }
  void router.push({
    name: 'search',
    query: {
      q: keyword
    }
  })
}

function openUploadDialog() {
  const pathId = route.name === 'folder' && typeof route.params.pathId === 'string' ? route.params.pathId : 'root'
  void router.push({
    name: 'folder',
    params: {
      pathId
    },
    query: {
      upload: '1'
    }
  })
}

watch(
  () => route.query.q,
  (value) => {
    if (route.name === 'search' && typeof value === 'string') {
      searchKeyword.value = value
    }
  },
  { immediate: true }
)
</script>

<template>
  <header class="top-nav">
    <div class="top-nav__left">
      <el-button
        text
        class="top-nav__icon-button"
        :icon="Fold"
        aria-label="折叠侧边目录"
        @click="emit('toggleSidebar')"
      />
      <RouterLink class="top-nav__brand" :to="{ name: 'dashboard' }">
        <span class="top-nav__mark">PF</span>
        <span>PFMT</span>
      </RouterLink>
      <el-breadcrumb class="top-nav__breadcrumb" separator="/">
        <el-breadcrumb-item :to="{ name: 'dashboard' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="top-nav__right">
      <el-input
        v-model="searchKeyword"
        class="top-nav__search"
        placeholder="搜索元数据"
        clearable
        @keyup.enter="submitSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <div v-if="settingsStore.hiddenFeatureEnabled" class="top-nav__hidden-switch">
        <span>显示隐藏</span>
        <el-switch
          :model-value="settingsStore.showHiddenContent"
          aria-label="显示隐藏内容"
          @change="(value: string | number | boolean) => void settingsStore.setShowHiddenContent(Boolean(value))"
        />
      </div>

      <el-tooltip content="上传文件" placement="bottom">
        <el-button :icon="UploadFilled" circle @click="openUploadDialog" />
      </el-tooltip>
      <el-tooltip content="系统配置" placement="bottom">
        <el-button :icon="Setting" circle @click="navigate('settings')" />
      </el-tooltip>

      <el-dropdown trigger="click">
        <button class="top-nav__user" type="button">
          <span>{{ displayName.slice(0, 1) }}</span>
          <strong>{{ displayName }}</strong>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item :icon="HomeFilled" @click="navigate('dashboard')">首页</el-dropdown-item>
            <el-dropdown-item :icon="FolderOpened" @click="openRootFolder">文件列表</el-dropdown-item>
            <el-dropdown-item divided :icon="SwitchButton" @click="handleLogout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.top-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--pfmt-topbar-height);
  padding: 0 18px;
  background: var(--pfmt-surface);
  border-bottom: 1px solid var(--pfmt-border-soft);
}

.top-nav__left,
.top-nav__right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.top-nav__icon-button {
  width: 34px;
  height: 34px;
}

.top-nav__brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  white-space: nowrap;
}

.top-nav__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  color: #ffffff;
  background: var(--pfmt-primary);
  font-size: 13px;
}

.top-nav__breadcrumb {
  min-width: 0;
}

.top-nav__search {
  width: 220px;
}

.top-nav__hidden-switch {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--pfmt-text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.top-nav__user {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  cursor: pointer;
  color: var(--pfmt-text);
}

.top-nav__user span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  color: #ffffff;
  background: #596b85;
  font-size: 13px;
}

.top-nav__user strong {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

@media (max-width: 920px) {
  .top-nav__breadcrumb,
  .top-nav__search,
  .top-nav__hidden-switch {
    display: none;
  }
}
</style>
