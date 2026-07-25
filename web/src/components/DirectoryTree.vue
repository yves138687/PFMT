<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { ElTree } from 'element-plus'
import { Folder, Refresh, Search } from '@element-plus/icons-vue'

import { usePathStore } from '@/stores/pathStore'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FilePathNode } from '@/types/files'

const router = useRouter()
const pathStore = usePathStore()
const settingsStore = useSettingsStore()
const filterText = ref('')
const treeRef = ref<InstanceType<typeof ElTree>>()

const treeProps = {
  label: 'path_name',
  children: 'children'
}

const emptyText = computed(() => (pathStore.loading ? '正在加载目录树' : '暂无目录'))

function filterNode(value: string, data: FilePathNode) {
  if (!value) {
    return true
  }

  return data.path_name.toLowerCase().includes(value.toLowerCase())
}

async function refreshTree() {
  await pathStore.loadTree(settingsStore.showHiddenContent)
}

function handleNodeClick(node: FilePathNode) {
  pathStore.selectPath(node.path_id)
  void router.push({
    name: 'folder',
    params: {
      pathId: node.path_id
    }
  })
}

function openUploadDialog() {
  void router.push({
    name: 'folder',
    params: {
      pathId: pathStore.selectedPath.path_id
    },
    query: {
      upload: '1'
    }
  })
}

watch(filterText, (value) => {
  treeRef.value?.filter(value)
})

watch(
  () => settingsStore.showHiddenContent,
  () => {
    void refreshTree()
  }
)

onMounted(() => {
  void refreshTree()
})
</script>

<template>
  <aside class="directory-tree">
    <div class="directory-tree__search">
      <el-input v-model="filterText" placeholder="筛选目录" clearable>
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-tooltip content="刷新目录树" placement="bottom">
        <el-button :icon="Refresh" circle :loading="pathStore.loading" @click="refreshTree" />
      </el-tooltip>
    </div>

    <el-scrollbar class="directory-tree__scroll">
      <el-tree
        ref="treeRef"
        :data="pathStore.tree"
        node-key="path_id"
        :props="treeProps"
        :filter-node-method="filterNode"
        :highlight-current="true"
        :default-expanded-keys="['root']"
        :empty-text="emptyText"
        @node-click="handleNodeClick"
      >
        <template #default="{ data }">
          <span class="directory-tree__node">
            <el-icon>
              <Folder />
            </el-icon>
            <span>{{ data.path_name }}</span>
            <small v-if="settingsStore.showHiddenContent && data.is_hidden">隐藏</small>
          </span>
        </template>
      </el-tree>
    </el-scrollbar>

    <div class="directory-tree__footer">
      <el-button type="primary" plain @click="openUploadDialog">上传文件</el-button>
      <el-button @click="router.push({ name: 'settings' })">系统配置</el-button>
    </div>
  </aside>
</template>

<style scoped>
.directory-tree {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--pfmt-surface);
  border-right: 1px solid var(--pfmt-border-soft);
}

.directory-tree__search {
  display: flex;
  gap: 8px;
  padding: 14px;
  border-bottom: 1px solid var(--pfmt-border-soft);
}

.directory-tree__scroll {
  flex: 1;
  padding: 8px;
}

.directory-tree__node {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  line-height: 28px;
}

.directory-tree__node span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.directory-tree__node small {
  padding: 1px 6px;
  border-radius: 999px;
  color: var(--pfmt-warning);
  background: #fff7ed;
  font-size: 12px;
}

.directory-tree__footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--pfmt-border-soft);
}
</style>
