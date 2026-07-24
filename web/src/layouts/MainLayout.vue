<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import DirectoryTree from '@/components/DirectoryTree.vue'
import TopNavigation from '@/components/TopNavigation.vue'
import { useSettingsStore } from '@/stores/settingsStore'

const settingsStore = useSettingsStore()
const sidebarCollapsed = ref(false)

const layoutClass = computed(() => ({
  'main-layout--collapsed': sidebarCollapsed.value
}))

onMounted(() => {
  void settingsStore.loadSettings()
})
</script>

<template>
  <div class="main-layout" :class="layoutClass">
    <TopNavigation
      :sidebar-collapsed="sidebarCollapsed"
      @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
    />

    <div class="main-layout__body">
      <DirectoryTree class="main-layout__sidebar" />
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
    grid-template-columns: minmax(0, 1fr);
  }

  .main-layout__sidebar {
    position: fixed;
    left: 0;
    z-index: 18;
    width: var(--pfmt-sidebar-width);
    box-shadow: 12px 0 30px rgb(15 23 42 / 12%);
  }

  .main-layout--collapsed .main-layout__sidebar {
    transform: translateX(-100%);
  }
}
</style>
