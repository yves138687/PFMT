<script setup lang="ts">
import { computed } from 'vue'
import { Tickets } from '@element-plus/icons-vue'

import type { DocumentOutlineItem } from '@/utils/documentOutline'

const props = defineProps<{
  items: DocumentOutlineItem[]
  activeId?: string
}>()

const emit = defineEmits<{
  navigate: [id: string, index: number]
}>()

const hasItems = computed(() => props.items.length > 0)
</script>

<template>
  <aside class="document-outline" aria-label="文档目录">
    <div class="document-outline__header">
      <el-icon><Tickets /></el-icon>
      <span>目录</span>
    </div>

    <nav v-if="hasItems" class="document-outline__list">
      <button
        v-for="(item, index) in items"
        :key="item.id"
        type="button"
        class="document-outline__item"
        :class="{ 'document-outline__item--active': item.id === activeId }"
        :style="{ paddingLeft: `${10 + (item.level - 1) * 12}px` }"
        :title="item.title"
        @click="emit('navigate', item.id, index)"
      >
        {{ item.title }}
      </button>
    </nav>
    <div v-else class="document-outline__empty">暂无目录</div>
  </aside>
</template>

<style scoped>
.document-outline {
  position: sticky;
  top: 16px;
  align-self: start;
  display: flex;
  flex-direction: column;
  width: 220px;
  max-height: calc(100vh - 132px);
  overflow: hidden;
  border: 1px solid var(--pfmt-border);
  border-radius: 8px;
  background: #fff;
}

.document-outline__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--pfmt-border);
  color: var(--pfmt-text);
  font-weight: 600;
}

.document-outline__list {
  display: grid;
  gap: 2px;
  padding: 8px 6px;
  overflow: auto;
}

.document-outline__item {
  width: 100%;
  min-height: 30px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pfmt-text-muted);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  line-height: 1.35;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-outline__item:hover {
  background: #f8fafc;
  color: var(--pfmt-text);
}

.document-outline__item--active {
  background: #ecf5ff;
  color: var(--el-color-primary);
  font-weight: 600;
}

.document-outline__empty {
  padding: 18px 14px;
  color: var(--pfmt-text-muted);
  font-size: 13px;
}

@media (max-width: 960px) {
  .document-outline {
    position: static;
    width: 100%;
    max-height: 220px;
  }
}
</style>
