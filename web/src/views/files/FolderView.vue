<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  Delete,
  DocumentAdd,
  FolderAdd,
  FolderDelete,
  InfoFilled,
  Rank,
  Refresh,
  UploadFilled,
  View
} from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { pathsApi } from '@/api/paths'
import FilePropertiesDialog from '@/components/FilePropertiesDialog.vue'
import { usePathStore } from '@/stores/pathStore'
import { useSettingsStore } from '@/stores/settingsStore'
import type { FileDetail, FileInfo, FilePathNode } from '@/types/files'
import { formatDateTime, formatFileSize } from '@/utils/format'

interface PathOption {
  label: string
  value: string
  fullPath: string
}

const route = useRoute()
const router = useRouter()
const pathStore = usePathStore()
const settingsStore = useSettingsStore()
const files = ref<FileInfo[]>([])
const loading = ref(false)
const propertiesVisible = ref(false)
const propertiesFile = ref<FileInfo | null>(null)
const createFolderVisible = ref(false)
const createFolderLoading = ref(false)
const moveFileVisible = ref(false)
const moveFileLoading = ref(false)
const movingFile = ref<FileInfo | null>(null)
const moveFileTargetPathId = ref('root')
const movePathVisible = ref(false)
const movePathLoading = ref(false)
const movePathTargetParentId = ref('root')
const createFolderForm = ref<{
  path_name: string
  description: string
  is_hidden: boolean
}>({
  path_name: '',
  description: '',
  is_hidden: false
})

const currentPathId = computed(() => (typeof route.params.pathId === 'string' ? route.params.pathId : 'root'))

const selectedPath = computed(() => pathStore.selectedPath)

const currentPathIsRoot = computed(() => currentPathId.value === 'root')

const pathOptions = computed(() => flattenPathOptions(pathStore.tree))

const currentSubtreePathIds = computed(() => {
  const ids = new Set<string>()
  collectPathIds(selectedPath.value, ids)
  return ids
})

const movePathOptions = computed(() =>
  pathOptions.value.filter((item) => !currentSubtreePathIds.value.has(item.value))
)

function canReadMarkdown(file: FileInfo) {
  return ['.md', '.markdown'].includes((file.file_ext ?? '').toLowerCase()) || file.mime_type === 'text/markdown'
}

function flattenPathOptions(nodes: FilePathNode[], ancestors: string[] = []): PathOption[] {
  return nodes.flatMap((node) => {
    const labelParts = [...ancestors, node.path_name]
    return [
      {
        label: labelParts.join(' / '),
        value: node.path_id,
        fullPath: node.full_path
      },
      ...flattenPathOptions(node.children ?? [], labelParts)
    ]
  })
}

function collectPathIds(node: FilePathNode | null | undefined, ids: Set<string>) {
  if (!node) {
    return
  }

  ids.add(node.path_id)
  const children = node.children ?? []
  children.forEach((child) => collectPathIds(child, ids))
}

function normalizeOptionalText(value: string) {
  const normalized = value.trim()
  return normalized ? normalized : null
}

async function ensurePathTree() {
  const hasCurrentPath = pathOptions.value.some((item) => item.value === currentPathId.value)
  if (!hasCurrentPath) {
    await pathStore.loadTree(settingsStore.showHiddenContent)
  }
}

function openFileDetail(file: FileInfo) {
  void router.push({
    name: 'file-detail',
    params: {
      fileId: file.file_id
    },
    query: {
      pathId: currentPathId.value
    }
  })
}

function openProperties(file: FileInfo) {
  propertiesFile.value = file
  propertiesVisible.value = true
}

function handleFileSaved(updatedFile: FileDetail) {
  files.value = files.value.map((item) => (item.file_id === updatedFile.file_id ? { ...item, ...updatedFile } : item))
}

async function openCreateFolder() {
  await ensurePathTree()
  createFolderForm.value = {
    path_name: '',
    description: '',
    is_hidden: selectedPath.value.is_hidden
  }
  createFolderVisible.value = true
}

async function createFolder() {
  const pathName = createFolderForm.value.path_name.trim()
  if (!pathName) {
    ElMessage.warning('请输入目录名称')
    return
  }

  createFolderLoading.value = true
  try {
    const created = await pathsApi.createPath({
      path_name: pathName,
      parent_path_id: currentPathId.value,
      path_type: 'normal',
      description: normalizeOptionalText(createFolderForm.value.description),
      is_hidden: createFolderForm.value.is_hidden
    })
    createFolderVisible.value = false
    ElMessage.success('目录已创建')
    await pathStore.loadTree(settingsStore.showHiddenContent)
    await router.push({
      name: 'folder',
      params: {
        pathId: created.path_id
      }
    })
  } finally {
    createFolderLoading.value = false
  }
}

async function openMoveFile(file: FileInfo) {
  await ensurePathTree()
  movingFile.value = file
  moveFileTargetPathId.value = file.path_id
  moveFileVisible.value = true
}

async function moveFile() {
  if (!movingFile.value) {
    return
  }

  if (moveFileTargetPathId.value === movingFile.value.path_id) {
    ElMessage.warning('请选择不同的目标目录')
    return
  }

  moveFileLoading.value = true
  try {
    await filesApi.moveFile(
      movingFile.value.file_id,
      moveFileTargetPathId.value,
      settingsStore.showHiddenContent
    )
    moveFileVisible.value = false
    ElMessage.success('文件已移动')
    await loadFiles()
  } finally {
    moveFileLoading.value = false
  }
}

async function deleteFile(file: FileInfo) {
  try {
    await ElMessageBox.confirm(`确认删除文件“${file.original_name}”？`, '删除文件', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger'
    })
  } catch {
    return
  }

  await filesApi.deleteFile(file.file_id, settingsStore.showHiddenContent)
  if (propertiesFile.value?.file_id === file.file_id) {
    propertiesVisible.value = false
    propertiesFile.value = null
  }
  ElMessage.success('文件已删除')
  await loadFiles()
}

async function openMovePath() {
  if (currentPathIsRoot.value) {
    return
  }

  await ensurePathTree()
  const parentPathId = selectedPath.value.parent_path_id ?? 'root'
  movePathTargetParentId.value = movePathOptions.value.some((item) => item.value === parentPathId)
    ? parentPathId
    : 'root'
  movePathVisible.value = true
}

async function movePath() {
  if (currentPathIsRoot.value) {
    return
  }

  if (movePathTargetParentId.value === selectedPath.value.parent_path_id) {
    ElMessage.warning('请选择新的父目录')
    return
  }

  movePathLoading.value = true
  try {
    const moved = await pathsApi.movePath(currentPathId.value, movePathTargetParentId.value)
    movePathVisible.value = false
    ElMessage.success('目录已移动')
    await pathStore.loadTree(settingsStore.showHiddenContent)
    await router.push({
      name: 'folder',
      params: {
        pathId: moved.path_id
      }
    })
  } finally {
    movePathLoading.value = false
  }
}

async function deleteCurrentPath() {
  if (currentPathIsRoot.value) {
    return
  }

  const path = selectedPath.value
  try {
    await ElMessageBox.confirm(`确认删除目录“${path.path_name}”及其中所有子目录和文件？`, '删除目录', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger'
    })
  } catch {
    return
  }

  await pathsApi.deletePath(currentPathId.value)
  ElMessage.success('目录已删除')
  await pathStore.loadTree(settingsStore.showHiddenContent)
  await router.push({
    name: 'folder',
    params: {
      pathId: path.parent_path_id ?? 'root'
    }
  })
}

async function loadFiles() {
  pathStore.selectPath(currentPathId.value)
  loading.value = true
  try {
    files.value = await filesApi.listFiles(currentPathId.value, settingsStore.showHiddenContent)
  } catch {
    files.value = []
  } finally {
    loading.value = false
  }
}

watch(
  [currentPathId, () => settingsStore.showHiddenContent],
  () => {
    void loadFiles()
  },
  { immediate: true }
)
</script>

<template>
  <section class="page-shell folder-view">
    <div class="page-heading">
      <div>
        <h1>{{ selectedPath.path_name }}</h1>
        <p>{{ selectedPath.full_path }}</p>
      </div>
      <div class="folder-view__actions">
        <el-button :icon="FolderAdd" @click="openCreateFolder">新建目录</el-button>
        <el-button :icon="DocumentAdd">新建文档</el-button>
        <el-button :icon="Rank" :disabled="currentPathIsRoot" @click="openMovePath">移动目录</el-button>
        <el-button type="danger" plain :icon="FolderDelete" :disabled="currentPathIsRoot" @click="deleteCurrentPath">
          删除目录
        </el-button>
        <el-button type="primary" :icon="UploadFilled" @click="router.push({ name: 'upload' })">上传</el-button>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>文件列表</h2>
        <div class="folder-view__toolbar">
          <el-button :icon="Refresh" :loading="loading" @click="loadFiles">刷新</el-button>
          <el-segmented :model-value="'list'" :options="['list', 'grid']" disabled />
        </div>
      </div>
      <div class="panel-body">
        <el-table v-loading="loading" :data="files" border empty-text="当前目录暂无文件">
          <el-table-column label="真实文件名" min-width="220">
            <template #default="{ row }">
              <span class="folder-view__file-name">
                <strong>{{ row.original_name }}</strong>
                <small v-if="row.remark">{{ row.remark }}</small>
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="file_type" label="文件类型" width="120" />
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at ?? row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="270" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="View" :disabled="!canReadMarkdown(row)" @click="openFileDetail(row)">
                查看
              </el-button>
              <el-button link :icon="InfoFilled" @click="openProperties(row)">
                属性
              </el-button>
              <el-button link :icon="Rank" @click="openMoveFile(row)">
                移动
              </el-button>
              <el-button link type="danger" :icon="Delete" @click="deleteFile(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <FilePropertiesDialog
      v-model="propertiesVisible"
      :file="propertiesFile"
      :show-hidden="settingsStore.showHiddenContent"
      @saved="handleFileSaved"
    />

    <el-dialog v-model="createFolderVisible" title="新建目录" width="460px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="目录名称">
          <el-input v-model="createFolderForm.path_name" maxlength="255" show-word-limit autofocus />
        </el-form-item>
        <el-form-item label="目录描述">
          <el-input v-model="createFolderForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="隐藏目录">
          <el-switch v-model="createFolderForm.is_hidden" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createFolderVisible = false">取消</el-button>
        <el-button type="primary" :loading="createFolderLoading" @click="createFolder">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="moveFileVisible" title="移动文件" width="460px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="目标目录">
          <el-select v-model="moveFileTargetPathId" filterable class="folder-view__path-select">
            <el-option v-for="item in pathOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moveFileVisible = false">取消</el-button>
        <el-button type="primary" :loading="moveFileLoading" @click="moveFile">移动</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="movePathVisible" title="移动目录" width="460px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="目标父目录">
          <el-select v-model="movePathTargetParentId" filterable class="folder-view__path-select">
            <el-option v-for="item in movePathOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="movePathVisible = false">取消</el-button>
        <el-button type="primary" :loading="movePathLoading" @click="movePath">移动</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.folder-view__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.folder-view__toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.folder-view__file-name {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.folder-view__file-name strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-view__file-name small {
  overflow: hidden;
  color: var(--pfmt-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-view__path-select {
  width: 100%;
}
</style>
