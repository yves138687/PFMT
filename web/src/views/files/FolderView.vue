<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  Close,
  Delete,
  DocumentAdd,
  Edit,
  FolderAdd,
  FolderDelete,
  InfoFilled,
  Rank,
  Refresh,
  UploadFilled,
  View,
  ZoomIn,
  ZoomOut
} from '@element-plus/icons-vue'

import { filesApi } from '@/api/files'
import { pathsApi } from '@/api/paths'
import FilePropertiesDialog from '@/components/FilePropertiesDialog.vue'
import FileUploadDialog from '@/components/FileUploadDialog.vue'
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
const moveFileTargetPathId = ref('root')
const selectedFiles = ref<FileInfo[]>([])
const movePathVisible = ref(false)
const movePathLoading = ref(false)
const movePathTargetParentId = ref('root')
const editPathVisible = ref(false)
const editPathLoading = ref(false)
const fileKeyword = ref('')
const tagFilter = ref<string[]>([])
const uploadVisible = ref(false)
const imagePreviewVisible = ref(false)
const imagePreviewIndex = ref(0)
const imagePreviewPathId = ref('')
const imagePreviewScale = ref(1)
const imagePreviewPanX = ref(0)
const imagePreviewPanY = ref(0)
const imagePreviewPanning = ref(false)
const imagePreviewPanStart = ref({ x: 0, y: 0, panX: 0, panY: 0 })
const imagePreviewLoadingIds = ref<Set<string>>(new Set())
const imagePreviewUrls = ref<Record<string, string>>({})
const videoPreviewVisible = ref(false)
const videoPreviewIndex = ref(0)
const videoPreviewPathId = ref('')
const videoPreviewUrl = ref('')
const videoPreviewLoading = ref(false)
const videoPreviewError = ref('')
const createFolderForm = ref<{
  path_name: string
  description: string
  is_hidden: boolean
}>({
  path_name: '',
  description: '',
  is_hidden: false
})
const editPathForm = ref<{
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
const tagOptions = computed(() => {
  const names = new Set<string>()
  files.value.forEach((file) => file.tags?.forEach((tag) => names.add(tag.tag_name)))
  return Array.from(names).sort((a, b) => a.localeCompare(b))
})
const filteredFiles = computed(() => {
  const keyword = fileKeyword.value.trim().toLowerCase()
  return files.value.filter((file) => {
    const matchesKeyword =
      !keyword ||
      file.original_name.toLowerCase().includes(keyword) ||
      (file.remark ?? '').toLowerCase().includes(keyword) ||
      (file.summary_content ?? '').toLowerCase().includes(keyword)
    const fileTags = new Set((file.tags ?? []).map((tag) => tag.tag_name))
    const matchesTags = tagFilter.value.every((tagName) => fileTags.has(tagName))
    return matchesKeyword && matchesTags
  })
})
const imageFiles = computed(() => files.value.filter((file) => file.file_type === 'image'))
const currentImageFile = computed(() => imageFiles.value[imagePreviewIndex.value] ?? null)
const currentImageUrl = computed(() => (currentImageFile.value ? imagePreviewUrls.value[currentImageFile.value.file_id] : ''))
const canShowPreviousImage = computed(() => imagePreviewIndex.value > 0)
const canShowNextImage = computed(() => imagePreviewIndex.value < imageFiles.value.length - 1)
const imagePreviewTransform = computed(
  () => `translate(${imagePreviewPanX.value}px, ${imagePreviewPanY.value}px) scale(${imagePreviewScale.value})`
)
const videoFiles = computed(() => files.value.filter((file) => file.file_type === 'video'))
const currentVideoFile = computed(() => videoFiles.value[videoPreviewIndex.value] ?? null)
const canShowPreviousVideo = computed(() => videoPreviewIndex.value > 0)
const canShowNextVideo = computed(() => videoPreviewIndex.value < videoFiles.value.length - 1)

function canOpenPreview(file: FileInfo) {
  return (
    file.file_type === 'text' ||
    ['.md', '.markdown'].includes((file.file_ext ?? '').toLowerCase()) ||
    file.mime_type === 'text/markdown' ||
    ['image', 'pdf', 'video'].includes(file.file_type)
  )
}

function tagNames(file: FileInfo) {
  return (file.tags ?? []).map((tag) => tag.tag_name).join('、')
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

async function openFileDetail(file: FileInfo) {
  if (file.file_type === 'image') {
    await openImagePreview(file)
    return
  }
  if (file.file_type === 'video') {
    await openVideoPreview(file)
    return
  }

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

async function openVideoPreview(file: FileInfo) {
  const index = videoFiles.value.findIndex((item) => item.file_id === file.file_id)
  if (index < 0) {
    return
  }

  videoPreviewIndex.value = index
  videoPreviewPathId.value = currentPathId.value
  videoPreviewVisible.value = true
  await loadVideoPreview(index)
}

async function selectVideoPreview(index: number) {
  if (index < 0 || index >= videoFiles.value.length || index === videoPreviewIndex.value) {
    return
  }

  videoPreviewIndex.value = index
  await loadVideoPreview(index)
}

function showPreviousVideo() {
  if (canShowPreviousVideo.value) {
    void selectVideoPreview(videoPreviewIndex.value - 1)
  }
}

function showNextVideo() {
  if (canShowNextVideo.value) {
    void selectVideoPreview(videoPreviewIndex.value + 1)
  }
}

async function loadVideoPreview(index: number) {
  const file = videoFiles.value[index]
  if (!file) {
    return
  }

  videoPreviewLoading.value = true
  videoPreviewError.value = ''
  videoPreviewUrl.value = ''
  try {
    const response = await filesApi.issuePreviewToken(file.file_id, settingsStore.showHiddenContent)
    videoPreviewUrl.value = new URL(response.preview_url, window.location.origin).toString()
  } finally {
    videoPreviewLoading.value = false
  }
}

function handleVideoError() {
  videoPreviewError.value = '当前浏览器不支持该视频编码或容器'
}

function closeVideoPreview() {
  videoPreviewVisible.value = false
  videoPreviewUrl.value = ''
  videoPreviewError.value = ''
  videoPreviewLoading.value = false
}

async function openImagePreview(file: FileInfo) {
  const index = imageFiles.value.findIndex((item) => item.file_id === file.file_id)
  if (index < 0) {
    return
  }

  imagePreviewIndex.value = index
  imagePreviewPathId.value = currentPathId.value
  resetImageZoom()
  imagePreviewVisible.value = true
  await loadImagePreviewAt(index)
  void loadImagePreviewNeighbors(index)
  void loadImagePreviewThumbnails()
}

async function selectImagePreview(index: number) {
  if (index < 0 || index >= imageFiles.value.length || index === imagePreviewIndex.value) {
    return
  }

  imagePreviewIndex.value = index
  resetImageZoom()
  await loadImagePreviewAt(index)
  void loadImagePreviewNeighbors(index)
}

function showPreviousImage() {
  if (canShowPreviousImage.value) {
    void selectImagePreview(imagePreviewIndex.value - 1)
  }
}

function showNextImage() {
  if (canShowNextImage.value) {
    void selectImagePreview(imagePreviewIndex.value + 1)
  }
}

function zoomImage(delta: number) {
  const nextScale = Math.min(4, Math.max(0.25, imagePreviewScale.value + delta))
  imagePreviewScale.value = Number(nextScale.toFixed(2))
  if (imagePreviewScale.value <= 1) {
    imagePreviewPanX.value = 0
    imagePreviewPanY.value = 0
  }
}

function resetImageZoom() {
  imagePreviewScale.value = 1
  imagePreviewPanX.value = 0
  imagePreviewPanY.value = 0
  imagePreviewPanning.value = false
}

function startImagePan(event: PointerEvent) {
  if (imagePreviewScale.value <= 1) {
    return
  }

  imagePreviewPanning.value = true
  imagePreviewPanStart.value = {
    x: event.clientX,
    y: event.clientY,
    panX: imagePreviewPanX.value,
    panY: imagePreviewPanY.value
  }
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
}

function moveImagePan(event: PointerEvent) {
  if (!imagePreviewPanning.value) {
    return
  }

  imagePreviewPanX.value = imagePreviewPanStart.value.panX + event.clientX - imagePreviewPanStart.value.x
  imagePreviewPanY.value = imagePreviewPanStart.value.panY + event.clientY - imagePreviewPanStart.value.y
}

function stopImagePan(event?: PointerEvent) {
  imagePreviewPanning.value = false
  if (event?.currentTarget instanceof HTMLElement) {
    try {
      event.currentTarget.releasePointerCapture(event.pointerId)
    } catch {
      // Pointer capture may already be released when the cursor leaves the image.
    }
  }
}

async function loadImagePreviewNeighbors(currentIndex: number) {
  await Promise.all([loadImagePreviewAt(currentIndex - 1), loadImagePreviewAt(currentIndex + 1)])
}

async function loadImagePreviewThumbnails() {
  await Promise.all(imageFiles.value.map((_file, index) => loadImagePreviewAt(index)))
}

async function loadImagePreviewAt(index: number) {
  const file = imageFiles.value[index]
  if (!file || imagePreviewUrls.value[file.file_id] || imagePreviewLoadingIds.value.has(file.file_id)) {
    return
  }

  imagePreviewLoadingIds.value = new Set([...imagePreviewLoadingIds.value, file.file_id])
  try {
    const blob = await filesApi.getPreviewBlob(file.file_id, settingsStore.showHiddenContent)
    const nextUrls = { ...imagePreviewUrls.value }
    nextUrls[file.file_id] = URL.createObjectURL(blob)
    imagePreviewUrls.value = nextUrls
  } finally {
    const nextLoadingIds = new Set(imagePreviewLoadingIds.value)
    nextLoadingIds.delete(file.file_id)
    imagePreviewLoadingIds.value = nextLoadingIds
  }
}

function closeImagePreview() {
  imagePreviewVisible.value = false
  resetImageZoom()
  clearImagePreviewUrls()
}

function clearImagePreviewUrls() {
  Object.values(imagePreviewUrls.value).forEach((url) => URL.revokeObjectURL(url))
  imagePreviewUrls.value = {}
  imagePreviewLoadingIds.value = new Set()
}

function openProperties(file: FileInfo) {
  propertiesFile.value = file
  propertiesVisible.value = true
}

function openCurrentImageProperties() {
  if (!currentImageFile.value) {
    return
  }
  const file = currentImageFile.value
  closeImagePreview()
  openProperties(file)
}

function openCurrentVideoProperties() {
  if (!currentVideoFile.value) {
    return
  }
  const file = currentVideoFile.value
  closeVideoPreview()
  openProperties(file)
}

async function openUploadDialog() {
  await ensurePathTree()
  uploadVisible.value = true
}

async function handleUploadCompleted() {
  await loadFiles()
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

async function openMoveSelectedFiles() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请先选择要移动的文件')
    return
  }
  await ensurePathTree()
  moveFileTargetPathId.value = currentPathId.value
  moveFileVisible.value = true
}

function handleSelectionChange(selection: FileInfo[]) {
  selectedFiles.value = selection
}

async function moveSelectedFiles() {
  if (!selectedFiles.value.length) {
    return
  }

  if (moveFileTargetPathId.value === currentPathId.value) {
    ElMessage.warning('请选择不同的目标目录')
    return
  }

  moveFileLoading.value = true
  try {
    await Promise.all(
      selectedFiles.value.map((file) =>
        filesApi.moveFile(file.file_id, moveFileTargetPathId.value, settingsStore.showHiddenContent)
      )
    )
    moveFileVisible.value = false
    ElMessage.success(`已移动 ${selectedFiles.value.length} 个文件`)
    selectedFiles.value = []
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
  if (file.file_type === 'image') {
    closeImagePreview()
  }
  if (file.file_type === 'video') {
    closeVideoPreview()
  }
  ElMessage.success('文件已删除')
  await loadFiles()
}

async function toggleFileHidden(file: FileInfo) {
  const targetHidden = !file.is_hidden
  const updated = await filesApi.updateFile(
    file.file_id,
    {
      is_hidden: targetHidden
    },
    settingsStore.showHiddenContent || targetHidden
  )
  ElMessage.success(targetHidden ? '文件已隐藏' : '文件已取消隐藏')
  handleFileSaved(updated)
  if (targetHidden && !settingsStore.showHiddenContent) {
    await loadFiles()
  }
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

function openEditPath() {
  if (currentPathIsRoot.value) {
    return
  }
  editPathForm.value = {
    path_name: selectedPath.value.path_name,
    description: selectedPath.value.description ?? '',
    is_hidden: selectedPath.value.is_hidden
  }
  editPathVisible.value = true
}

async function savePathMetadata() {
  if (currentPathIsRoot.value) {
    return
  }
  const pathName = editPathForm.value.path_name.trim()
  if (!pathName) {
    ElMessage.warning('请输入目录名称')
    return
  }

  editPathLoading.value = true
  try {
    const updated = await pathsApi.updatePath(currentPathId.value, {
      path_name: pathName,
      description: normalizeOptionalText(editPathForm.value.description),
      is_hidden: editPathForm.value.is_hidden
    })
    editPathVisible.value = false
    ElMessage.success('目录属性已保存')
    await pathStore.loadTree(settingsStore.showHiddenContent || updated.is_hidden)
    if (updated.is_hidden && !settingsStore.showHiddenContent) {
      await router.push({ name: 'folder', params: { pathId: updated.parent_path_id ?? 'root' } })
    }
  } finally {
    editPathLoading.value = false
  }
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
  if (imagePreviewVisible.value && imagePreviewPathId.value !== currentPathId.value) {
    closeImagePreview()
  }
  if (videoPreviewVisible.value && videoPreviewPathId.value !== currentPathId.value) {
    closeVideoPreview()
  }
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

watch(
  () => route.query.upload,
  (value) => {
    if (value === '1') {
      void openUploadDialog()
      void router.replace({
        name: 'folder',
        params: {
          pathId: currentPathId.value
        },
        query: {
          ...route.query,
          upload: undefined
        }
      })
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  clearImagePreviewUrls()
  closeVideoPreview()
})
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
        <el-button :icon="Edit" :disabled="currentPathIsRoot" @click="openEditPath">编辑目录</el-button>
        <el-button :icon="Rank" :disabled="currentPathIsRoot" @click="openMovePath">移动目录</el-button>
        <el-button type="danger" plain :icon="FolderDelete" :disabled="currentPathIsRoot" @click="deleteCurrentPath">
          删除目录
        </el-button>
        <el-button type="primary" :icon="UploadFilled" @click="openUploadDialog">上传</el-button>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>文件列表</h2>
        <div class="folder-view__toolbar">
          <el-input v-model="fileKeyword" clearable placeholder="筛选文件名、备注、摘要" class="folder-view__filter" />
          <el-select v-model="tagFilter" multiple clearable collapse-tags placeholder="标签筛选" class="folder-view__filter">
            <el-option v-for="tagName in tagOptions" :key="tagName" :label="tagName" :value="tagName" />
          </el-select>
          <el-button :icon="Rank" :disabled="!selectedFiles.length" @click="openMoveSelectedFiles">
            移动所选
          </el-button>
          <el-button :icon="Refresh" :loading="loading" @click="loadFiles">刷新</el-button>
          <el-segmented :model-value="'list'" :options="['list', 'grid']" disabled />
        </div>
      </div>
      <div class="panel-body">
        <el-table
          v-loading="loading"
          :data="filteredFiles"
          border
          empty-text="当前目录暂无文件"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="46" />
          <el-table-column label="真实文件名" min-width="220">
            <template #default="{ row }">
              <span class="folder-view__file-name">
                <strong>{{ row.original_name }}</strong>
                <small v-if="row.remark">{{ row.remark }}</small>
                <small v-if="row.tags?.length">{{ tagNames(row) }}</small>
              </span>
            </template>
          </el-table-column>
          <el-table-column v-if="settingsStore.showHiddenContent" label="状态" width="90">
            <template #default="{ row }">{{ row.is_hidden ? '隐藏' : '显示' }}</template>
          </el-table-column>
          <el-table-column prop="file_type" label="文件类型" width="120" />
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at ?? row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="View" :disabled="!canOpenPreview(row)" @click="openFileDetail(row)">
                查看
              </el-button>
              <el-button link :icon="InfoFilled" @click="openProperties(row)">
                属性
              </el-button>
              <el-button link :icon="View" @click="toggleFileHidden(row)">
                {{ row.is_hidden ? '显示' : '隐藏' }}
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

    <FileUploadDialog
      v-model="uploadVisible"
      :target-path-id="currentPathId"
      :target-full-path="selectedPath.full_path"
      @uploaded="handleUploadCompleted"
    />

    <Teleport to="body">
      <div v-if="imagePreviewVisible" class="image-viewer">
        <div class="image-viewer__topbar">
          <div class="image-viewer__title">
            <strong>{{ currentImageFile?.original_name }}</strong>
            <span>{{ imagePreviewIndex + 1 }} / {{ imageFiles.length }}</span>
          </div>
          <div class="image-viewer__tools">
            <el-button circle plain :icon="ZoomOut" :disabled="imagePreviewScale <= 0.25" @click="zoomImage(-0.25)" />
            <span class="image-viewer__scale">{{ Math.round(imagePreviewScale * 100) }}%</span>
            <el-button circle plain :icon="ZoomIn" :disabled="imagePreviewScale >= 4" @click="zoomImage(0.25)" />
            <el-button plain @click="resetImageZoom">适应窗口</el-button>
            <el-button v-if="currentImageFile" plain @click="openCurrentImageProperties">属性</el-button>
            <el-button circle plain :icon="Close" @click="closeImagePreview" />
          </div>
        </div>

        <div class="image-viewer__main">
          <el-button
            circle
            plain
            class="image-viewer__nav image-viewer__nav--left"
            :icon="ArrowLeft"
            :disabled="!canShowPreviousImage"
            @click="showPreviousImage"
          />
          <div class="image-viewer__canvas">
            <div v-if="currentImageUrl && currentImageFile" class="image-viewer__zoom-surface">
              <img
                class="image-viewer__image"
                :class="{
                  'image-viewer__image--zoomed': imagePreviewScale > 1,
                  'image-viewer__image--panning': imagePreviewPanning
                }"
                :src="currentImageUrl"
                :alt="currentImageFile.original_name"
                :style="{ transform: imagePreviewTransform }"
                draggable="false"
                @pointerdown.prevent="startImagePan"
                @pointermove.prevent="moveImagePan"
                @pointerup="stopImagePan"
                @pointercancel="stopImagePan"
                @lostpointercapture="stopImagePan"
              />
            </div>
            <el-skeleton v-else animated class="image-viewer__skeleton">
              <template #template>
                <el-skeleton-item variant="image" class="image-viewer__skeleton-item" />
              </template>
            </el-skeleton>
          </div>
          <el-button
            circle
            plain
            class="image-viewer__nav image-viewer__nav--right"
            :icon="ArrowRight"
            :disabled="!canShowNextImage"
            @click="showNextImage"
          />
        </div>

        <div class="image-viewer__thumbs" aria-label="图片缩略图列表">
          <button
            v-for="(file, index) in imageFiles"
            :key="file.file_id"
            type="button"
            class="image-viewer__thumb"
            :class="{ 'image-viewer__thumb--active': index === imagePreviewIndex }"
            :title="file.original_name"
            @click="selectImagePreview(index)"
          >
            <img v-if="imagePreviewUrls[file.file_id]" :src="imagePreviewUrls[file.file_id]" :alt="file.original_name" />
            <span v-else />
          </button>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="videoPreviewVisible" class="video-viewer">
        <div class="video-viewer__topbar">
          <div class="video-viewer__title">
            <strong>{{ currentVideoFile?.original_name }}</strong>
            <span>{{ videoPreviewIndex + 1 }} / {{ videoFiles.length }}</span>
          </div>
          <div class="video-viewer__tools">
            <el-button v-if="currentVideoFile" plain @click="openCurrentVideoProperties">属性</el-button>
            <el-button circle plain :icon="Close" @click="closeVideoPreview" />
          </div>
        </div>

        <div class="video-viewer__main">
          <el-button
            circle
            plain
            class="video-viewer__nav video-viewer__nav--left"
            :icon="ArrowLeft"
            :disabled="!canShowPreviousVideo"
            @click="showPreviousVideo"
          />
          <div v-loading="videoPreviewLoading" class="video-viewer__stage">
            <video
              v-if="videoPreviewUrl && currentVideoFile"
              :key="videoPreviewUrl"
              class="video-viewer__video"
              :src="videoPreviewUrl"
              controls
              preload="metadata"
              playsinline
              @error="handleVideoError"
            />
            <el-empty v-else-if="videoPreviewError" :description="videoPreviewError" />
            <el-empty v-else description="正在准备视频播放" />
            <p v-if="videoPreviewError" class="video-viewer__error">{{ videoPreviewError }}</p>
          </div>
          <el-button
            circle
            plain
            class="video-viewer__nav video-viewer__nav--right"
            :icon="ArrowRight"
            :disabled="!canShowNextVideo"
            @click="showNextVideo"
          />
        </div>

        <div class="video-viewer__items" aria-label="视频列表">
          <button
            v-for="(file, index) in videoFiles"
            :key="file.file_id"
            type="button"
            class="video-viewer__item"
            :class="{ 'video-viewer__item--active': index === videoPreviewIndex }"
            :title="file.original_name"
            @click="selectVideoPreview(index)"
          >
            <View class="video-viewer__item-icon" />
            <span>{{ file.original_name }}</span>
          </button>
        </div>
      </div>
    </Teleport>

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

    <el-dialog v-model="moveFileVisible" title="移动所选文件" width="460px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="已选择">
          <span class="muted">{{ selectedFiles.length }} 个文件</span>
        </el-form-item>
        <el-form-item label="目标目录">
          <el-select v-model="moveFileTargetPathId" filterable class="folder-view__path-select">
            <el-option v-for="item in pathOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moveFileVisible = false">取消</el-button>
        <el-button type="primary" :loading="moveFileLoading" @click="moveSelectedFiles">移动</el-button>
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

    <el-dialog v-model="editPathVisible" title="编辑目录" width="460px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="目录名称">
          <el-input v-model="editPathForm.path_name" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="目录描述">
          <el-input v-model="editPathForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="隐藏目录">
          <el-switch v-model="editPathForm.is_hidden" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editPathVisible = false">取消</el-button>
        <el-button type="primary" :loading="editPathLoading" @click="savePathMetadata">保存</el-button>
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

.folder-view__filter {
  width: 210px;
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

.image-viewer {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 12px;
  box-sizing: border-box;
  width: 100vw;
  height: 100dvh;
  padding: 14px 18px 18px;
  overflow: hidden;
  background: rgb(10 15 25 / 92%);
  color: #f8fafc;
}

.image-viewer__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.image-viewer__title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.image-viewer__title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-viewer__title span,
.image-viewer__scale {
  flex: 0 0 auto;
  color: rgb(226 232 240 / 74%);
}

.image-viewer__tools {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.image-viewer__main {
  position: relative;
  display: grid;
  min-height: 0;
}

.image-viewer__canvas {
  display: grid;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  place-items: center;
}

.image-viewer__zoom-surface {
  display: grid;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  place-items: center;
}

.image-viewer__image {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transform-origin: center center;
  user-select: none;
  transition: transform 120ms ease;
}

.image-viewer__image--zoomed {
  cursor: grab;
}

.image-viewer__image--panning {
  cursor: grabbing;
  transition: none;
}

.image-viewer__nav {
  position: absolute;
  top: 50%;
  z-index: 1;
  transform: translateY(-50%);
}

.image-viewer__nav--left {
  left: 8px;
}

.image-viewer__nav--right {
  right: 8px;
}

.image-viewer__skeleton {
  width: min(860px, 82vw);
}

.image-viewer__skeleton-item {
  width: 100%;
  height: min(62vh, 620px);
}

.image-viewer__thumbs {
  display: flex;
  gap: 10px;
  min-height: 84px;
  padding: 8px 0 2px;
  overflow-x: auto;
  justify-content: center;
}

.image-viewer__thumb {
  width: 74px;
  height: 74px;
  flex: 0 0 auto;
  padding: 0;
  overflow: hidden;
  background: rgb(30 41 59 / 82%);
  border: 2px solid transparent;
  border-radius: 6px;
  cursor: pointer;
}

.image-viewer__thumb--active {
  border-color: #60a5fa;
}

.image-viewer__thumb img,
.image-viewer__thumb span {
  display: block;
  width: 100%;
  height: 100%;
}

.image-viewer__thumb img {
  object-fit: cover;
}

@media (max-width: 720px) {
  .image-viewer {
    padding: 10px;
  }

  .image-viewer__topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .image-viewer__tools {
    flex-wrap: wrap;
  }

  .image-viewer__thumbs {
    justify-content: flex-start;
  }
}

.video-viewer {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 12px;
  box-sizing: border-box;
  width: 100vw;
  height: 100dvh;
  padding: 14px 18px 18px;
  overflow: hidden;
  background: rgb(10 15 25 / 92%);
  color: #f8fafc;
}

.video-viewer__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.video-viewer__title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.video-viewer__title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-viewer__title span {
  flex: 0 0 auto;
  color: rgb(226 232 240 / 74%);
}

.video-viewer__tools {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.video-viewer__main {
  position: relative;
  display: grid;
  min-height: 0;
}

.video-viewer__stage {
  display: grid;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  place-items: center;
}

.video-viewer__video {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  background: #000;
}

.video-viewer__error {
  position: absolute;
  right: 18px;
  bottom: 104px;
  margin: 0;
  padding: 8px 12px;
  color: #fecaca;
  background: rgb(127 29 29 / 80%);
  border-radius: 6px;
}

.video-viewer__nav {
  position: absolute;
  top: 50%;
  z-index: 1;
  transform: translateY(-50%);
}

.video-viewer__nav--left {
  left: 8px;
}

.video-viewer__nav--right {
  right: 8px;
}

.video-viewer__items {
  display: flex;
  gap: 10px;
  min-height: 72px;
  padding: 8px 0 2px;
  overflow-x: auto;
  justify-content: center;
}

.video-viewer__item {
  display: grid;
  width: 148px;
  height: 64px;
  flex: 0 0 auto;
  grid-template-columns: 24px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  color: #e2e8f0;
  background: rgb(30 41 59 / 82%);
  border: 2px solid transparent;
  border-radius: 6px;
  cursor: pointer;
}

.video-viewer__item--active {
  border-color: #60a5fa;
}

.video-viewer__item span {
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-viewer__item-icon {
  width: 18px;
  height: 18px;
}

@media (max-width: 720px) {
  .video-viewer {
    padding: 10px;
  }

  .video-viewer__topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .video-viewer__tools {
    flex-wrap: wrap;
  }

  .video-viewer__items {
    justify-content: flex-start;
  }
}
</style>
