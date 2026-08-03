<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DirectoryTree from '@/components/DirectoryTree.vue'
import TopNavigation from '@/components/TopNavigation.vue'
import { useSettingsStore } from '@/stores/settingsStore'

const MOBILE_QUERY = '(max-width: 820px)'

const settingsStore = useSettingsStore()
const route = useRoute()

function detectMobileViewport() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_QUERY).matches
}

const isMobileViewport = ref(detectMobileViewport())
const sidebarCollapsed = ref(isMobileViewport.value)
let mobileMediaQuery: MediaQueryList | null = null

const layoutClass = computed(() => ({
  'main-layout--collapsed': sidebarCollapsed.value,
  'main-layout--mobile': isMobileViewport.value,
  'main-layout--mobile-sidebar-open': isMobileViewport.value && !sidebarCollapsed.value
}))

function handleViewportChange(event?: MediaQueryListEvent | MediaQueryList) {
  const matches = event?.matches ?? mobileMediaQuery?.matches ?? false
  const wasMobile = isMobileViewport.value
  isMobileViewport.value = matches

  if (matches && !wasMobile) {
    sidebarCollapsed.value = true
  } else if (!matches && wasMobile) {
    sidebarCollapsed.value = false
  }
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function closeMobileSidebar() {
  if (isMobileViewport.value) {
    sidebarCollapsed.value = true
  }
}

onMounted(() => {
  void settingsStore.loadSettings()
  mobileMediaQuery = window.matchMedia(MOBILE_QUERY)
  handleViewportChange(mobileMediaQuery)
  mobileMediaQuery.addEventListener('change', handleViewportChange)
})

onBeforeUnmount(() => {
  mobileMediaQuery?.removeEventListener('change', handleViewportChange)
  document.body.classList.remove('pfmt-mobile-sidebar-open')
})

watch(
  () => route.fullPath,
  () => {
    closeMobileSidebar()
  }
)

watch(isMobileViewport, (value) => {
  document.body.classList.toggle('pfmt-mobile-sidebar-open', value && !sidebarCollapsed.value)
})

watch(sidebarCollapsed, (value) => {
  document.body.classList.toggle('pfmt-mobile-sidebar-open', isMobileViewport.value && !value)
})
</script>

<template>
  <div class="main-layout" :class="layoutClass">
    <TopNavigation
      :sidebar-collapsed="sidebarCollapsed"
      @toggle-sidebar="toggleSidebar"
    />

    <div class="main-layout__body">
      <button
        v-if="isMobileViewport && !sidebarCollapsed"
        class="main-layout__scrim"
        type="button"
        aria-label="关闭目录"
        @click="closeMobileSidebar"
      />
      <DirectoryTree class="main-layout__sidebar" @navigate="closeMobileSidebar" />
      <main class="main-layout__content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.main-layout {
  min-height: 100vh;
  background: var(--pfmt-bg);
}

.main-layout__body {
  display: grid;
  grid-template-columns: var(--pfmt-sidebar-width) minmax(0, 1fr);
  min-height: calc(100vh - var(--pfmt-topbar-height));
}

.main-layout__scrim {
  display: none;
}

.main-layout__sidebar {
  position: sticky;
  top: var(--pfmt-topbar-height);
  height: calc(100vh - var(--pfmt-topbar-height));
  transition:
    width 0.2s ease,
    transform 0.2s ease;
}

.main-layout__content {
  min-width: 0;
  padding: 22px;
}

.main-layout--collapsed .main-layout__body {
  grid-template-columns: 0 minmax(0, 1fr);
}

.main-layout--collapsed .main-layout__sidebar {
  overflow: hidden;
  width: 0;
  transform: translateX(-100%);
}

@media (max-width: 820px) {
  .main-layout__body,
  .main-layout--collapsed .main-layout__body {
    display: block;
    grid-template-columns: minmax(0, 1fr);
  }

  .main-layout__scrim {
    position: fixed;
    inset: var(--pfmt-topbar-height) 0 0;
    z-index: 17;
    display: block;
    padding: 0;
    border: 0;
    background: rgb(15 23 42 / 28%);
    backdrop-filter: blur(1px);
  }

  .main-layout__sidebar {
    position: fixed;
    left: 0;
    bottom: 0;
    z-index: 18;
    width: min(var(--pfmt-sidebar-width), calc(100vw - 48px));
    height: calc(100vh - var(--pfmt-topbar-height));
    transform: translateX(-100%);
    box-shadow: 12px 0 30px rgb(15 23 42 / 12%);
  }

  .main-layout--collapsed .main-layout__sidebar {
    width: min(var(--pfmt-sidebar-width), calc(100vw - 48px));
    transform: translateX(-100%);
  }

  .main-layout--mobile-sidebar-open .main-layout__sidebar {
    transform: translateX(0);
  }

  .main-layout__content {
    padding: 14px;
  }
}
</style>
