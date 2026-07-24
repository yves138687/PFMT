<script setup lang="ts">
import { computed } from 'vue'
import { Document, Files, FolderOpened, Key, UploadFilled, View } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { usePathStore } from '@/stores/pathStore'
import { useSettingsStore } from '@/stores/settingsStore'

const router = useRouter()
const pathStore = usePathStore()
const settingsStore = useSettingsStore()

const stats = computed(() => [
  { label: '文件总数', value: '0', note: '等待文件元数据接口接入', icon: Files },
  { label: '目录总数', value: String(pathStore.tree.length), note: '来自当前目录树根层级', icon: FolderOpened },
  { label: 'Markdown', value: '0', note: '首阶段查看能力已预留', icon: Document },
  {
    label: '加密状态',
    value: settingsStore.encryptionEnabled ? '启用' : '关闭',
    note: '由 storage.encryption_enabled 控制',
    icon: Key
  }
])

const quickActions = [
  { label: '上传文件', name: 'upload', icon: UploadFilled },
  { label: '系统配置', name: 'settings', icon: Key },
  { label: 'Markdown 查看', name: 'markdown', icon: View }
]
</script>

<template>
  <section class="page-shell">
    <div class="page-heading">
      <div>
        <h1>首页</h1>
        <p>第一阶段工作台，聚焦登录、配置、上传、目录树和 Markdown 查看。</p>
      </div>
    </div>

    <div class="dashboard__stats">
      <article v-for="item in stats" :key="item.label" class="dashboard__stat">
        <el-icon><component :is="item.icon" /></el-icon>
        <div>
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.note }}</small>
        </div>
      </article>
    </div>

    <section class="work-panel dashboard__section">
      <div class="panel-header">
        <h2>最近访问</h2>
        <span class="muted">隐藏内容默认不展示</span>
      </div>
      <div class="panel-body">
        <el-empty description="最近访问列表将在文件详情接口接入后展示" />
      </div>
    </section>

    <section class="work-panel dashboard__section">
      <div class="panel-header">
        <h2>快捷入口</h2>
      </div>
      <div class="dashboard__actions panel-body">
        <el-button
          v-for="action in quickActions"
          :key="action.name"
          :icon="action.icon"
          type="primary"
          plain
          @click="router.push({ name: action.name })"
        >
          {{ action.label }}
        </el-button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.dashboard__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.dashboard__stat {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding: 16px;
  background: var(--pfmt-surface);
  border: 1px solid var(--pfmt-border-soft);
  border-radius: 8px;
}

.dashboard__stat .el-icon {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  color: var(--pfmt-primary);
  background: var(--pfmt-primary-soft);
  font-size: 21px;
}

.dashboard__stat span,
.dashboard__stat small {
  display: block;
  color: var(--pfmt-text-muted);
}

.dashboard__stat strong {
  display: block;
  margin: 2px 0;
  font-size: 22px;
  line-height: 1.3;
}

.dashboard__stat small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.dashboard__section {
  margin-top: 16px;
}

.dashboard__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 1000px) {
  .dashboard__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .dashboard__stats {
    grid-template-columns: 1fr;
  }
}
</style>
