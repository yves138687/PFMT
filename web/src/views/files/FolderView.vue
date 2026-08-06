<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowDown,
  ArrowRight,
  Close,
  Delete,
  DocumentAdd,
  Download,
  Edit,
  Filter,
  FolderAdd,
  FolderDelete,
  InfoFilled,
  MoreFilled,
  Operation,
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
import type { DocumentFormat, FileDetail, FileInfo, FilePathNode } from '@/types/files'
import { saveBlobResponse } from '@/utils/download'
import { formatDateTime, formatFileSize } from '@/utils/format'

type FileViewMode = 'list' | 'grid'
type FileActionCommand = 'export' | 'properties' | 'toggle-hidden' | 'delete'
type PathActionCommand = 'create-folder' | 'create-document' | 'edit-path' | 'move-path' | 'delete-path'

interface PathOption {
  label: string
  value: string
  fullPath: string
}

interface FileActionItem {
  command: FileActionCommand
  label: string
  icon: Component
  danger?: boolean
}

const MOBILE_QUERY = '(max-width: 820px)'

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
const createDocumentVisible = ref(false)
const createDocumentLoading = ref(false)
const moveFileVisible = ref(false)
const moveFileLoading = ref(false)
const exportFilesLoading = ref(false)
const moveFileTargetPathId = ref('root')
const selectedFiles = ref<FileInfo[]>([])
const fileTableRef = ref<{
  clearSelection: () => void
  toggleRowSelection: (row: FileInfo, selected?: boolean) => void
} | null>(null)
const syncingTableSelection = ref(false)
const mergeDocumentVisible = ref(false)
const mergeDocumentLoading = ref(false)
const mergeDocumentForm = ref<{
  target_name: string
  target_format: DocumentFormat
}>({
  target_name: '合并文档.md',
  target_format: 'markdown'
})
const movePathVisible = ref(false)
const movePathLoading = ref(false)
const movePathTargetParentId = ref('root')
const editPathVisible = ref(false)
const editPathLoading = ref(false)
const fileKeyword = ref('')
const tagFilter = ref<string[]>([])
const fileTypeFilter = ref<string[]>([])
const viewMode = ref<FileViewMode>('list')
const isMobileViewport = ref(detectMobileViewport())
const activeActionFile = ref<FileInfo | null>(null)
const fileActionsDrawerVisible = ref(false)
const filterDrawerVisible = ref(false)
const batchActionsDrawerVisible = ref(false)
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
const createDocumentForm = ref<{
  original_name: string
  document_format: DocumentFormat
  is_hidden: boolean
}>({
  original_name: '未命名.md',
  document_format: 'markdown',
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
let mobileMediaQuery: MediaQueryList | null = null

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
const fileTypeOptions = [
  { label: '文本', value: 'text' },
  { label: '图片', value: 'image' },
  { label: 'PDF', value: 'pdf' },
  { label: '视频', value: 'video' },
  { label: '音频', value: 'audio' },
  { label: '其他', value: 'other' }
]
const viewModeOptions = [
  { label: '列表', value: 'list' },
  { label: '图标', value: 'grid' }
]
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
    const matchesType = fileTypeFilter.value.length === 0 || fileTypeFilter.value.includes(file.file_type)
    return matchesKeyword && matchesTags && matchesType
  })
})
const selectedFileIds = computed(() => new Set(selectedFiles.value.map((file) => file.file_id)))
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
const selectedDocumentFiles = computed(() => selectedFiles.value.filter((file) => file.file_type === 'text'))
const canMergeSelectedDocuments = computed(
  () => selectedFiles.value.length >= 2 && selectedDocumentFiles.value.length === selectedFiles.value.length
)
const activeFileActions = computed(() => (activeActionFile.value ? fileActionItems(activeActionFile.value) : []))

function detectMobileViewport() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_QUERY).matches
}

function handleViewportChange(event?: MediaQueryListEvent | MediaQueryList) {
  isMobileViewport.value = event?.matches ?? mobileMediaQuery?.matches ?? false
  if (!isMobileViewport.value) {
    filterDrawerVisible.value = false
    batchActionsDrawerVisible.value = false
    fileActionsDrawerVisible.value = false
  }
  void nextTick(syncTableSelection)
}

function fileActionItems(file: FileInfo): FileActionItem[] {
  return [
    {
      command: 'export',
      label: '导出',
      icon: Download
    },
    {
      command: 'properties',
      label: '属性',
      icon: InfoFilled
    },
    {
      command: 'toggle-hidden',
      label: file.is_hidden ? '显示' : '隐藏',
      icon: View
    },
    {
      command: 'delete',
      label: '删除',
      icon: Delete,
      danger: true
    }
  ]
}

function isFileActionCommand(command: unknown): command is FileActionCommand {
  return command === 'export' || command === 'properties' || command === 'toggle-hidden' || command === 'delete'
}

function isPathActionCommand(command: unknown): command is PathActionCommand {
  return (
    command === 'create-folder' ||
    command === 'create-document' ||
    command === 'edit-path' ||
    command === 'move-path' ||
    command === 'delete-path'
  )
}

function tagNames(file: FileInfo) {
  return (file.tags ?? []).map((tag) => tag.tag_name).join('、')
}

function fileTypeText(fileType: FileInfo['file_type']) {
  const item = fileTypeOptions.find((option) => option.value === fileType)
  return item?.label ?? '其他'
}

function defaultDocumentName(format: DocumentFormat) {
  if (format === 'plain_text') {
    return '未命名.txt'
  }
  if (format === 'html') {
    return '未命名.html'
  }
  return '未命名.md'
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

function isFileSelected(file: FileInfo) {
  return selectedFileIds.value.has(file.file_id)
}

function toggleGridFileSelection(file: FileInfo, selected: boolean) {
  if (selected) {
    if (!isFileSelected(file)) {
      selectedFiles.value = [...selectedFiles.value, file]
    }
    return
  }
  selectedFiles.value = selectedFiles.value.filter((item) => item.file_id !== file.file_id)
}

async function syncTableSelection() {
  if (viewMode.value !== 'list' || !fileTableRef.value) {
    return
  }
  syncingTableSelection.value = true
  try {
    fileTableRef.value.clearSelection()
    filteredFiles.value.forEach((file) => {
      if (selectedFileIds.value.has(file.file_id)) {
        fileTableRef.value?.toggleRowSelection(file, true)
      }
    })
  } finally {
    await nextTick()
    syncingTableSelection.value = false
  }
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
  if (file.file_type === 'text') {
    void router.push({
      name: 'document',
      params: {
        fileId: file.file_id
      },
      query: {
        pathId: currentPathId.value
      }
    })
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

function openFileActions(file: FileInfo) {
  activeActionFile.value = file
  fileActionsDrawerVisible.value = true
}

async function handleFileAction(file: FileInfo, command: unknown) {
  if (!isFileActionCommand(command)) {
    return
  }

  fileActionsDrawerVisible.value = false
  activeActionFile.value = null
  if (command === 'export') {
    await exportSingleFile(file)
    return
  }
  if (command === 'properties') {
    openProperties(file)
    return
  }
  if (command === 'toggle-hidden') {
    await toggleFileHidden(file)
    return
  }
  await deleteFile(file)
}

function handleActiveFileAction(command: FileActionCommand) {
  if (!activeActionFile.value) {
    return
  }
  void handleFileAction(activeActionFile.value, command)
}

function handlePathAction(command: unknown) {
  if (!isPathActionCommand(command)) {
    return
  }

  if (command === 'create-folder') {
    void openCreateFolder()
    return
  }
  if (command === 'create-document') {
    void openCreateDocument()
    return
  }
  if (command === 'edit-path') {
    openEditPath()
    return
  }
  if (command === 'move-path') {
    void openMovePath()
    return
  }
  void deleteCurrentPath()
}

function clearFilters() {
  fileTypeFilter.value = []
  tagFilter.value = []
}

async function openMoveSelectedFilesFromDrawer() {
  batchActionsDrawerVisible.value = false
  await openMoveSelectedFiles()
}

async function exportSelectedFilesFromDrawer() {
  batchActionsDrawerVisible.value = false
  await exportSelectedFiles()
}

function openMergeSelectedDocumentsFromDrawer() {
  batchActionsDrawerVisible.value = false
  openMergeSelectedDocuments()
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

async function openCreateDocument() {
  await ensurePathTree()
  createDocumentForm.value = {
    original_name: defaultDocumentName('markdown'),
    document_format: 'markdown',
    is_hidden: selectedPath.value.is_hidden
  }
  createDocumentVisible.value = true
}

function handleCreateDocumentFormatChange(value: string | number | boolean | undefined) {
  if (value !== 'plain_text' && value !== 'markdown' && value !== 'html') {
    return
  }
  createDocumentForm.value.document_format = value
  createDocumentForm.value.original_name = defaultDocumentName(value)
}

async function createDocument() {
  const originalName = createDocumentForm.value.original_name.trim()
  if (!originalName) {
    ElMessage.warning('请输入文档名称')
    return
  }

  createDocumentLoading.value = true
  try {
    const created = await filesApi.createDocument({
      path_id: currentPathId.value,
      original_name: originalName,
      document_format: createDocumentForm.value.document_format,
      is_hidden: createDocumentForm.value.is_hidden
    })
    createDocumentVisible.value = false
    ElMessage.success('文档已创建')
    await loadFiles()
    void router.push({
      name: 'document',
      params: {
        fileId: created.file_id
      },
      query: {
        pathId: created.path_id
      }
    })
  } finally {
    createDocumentLoading.value = false
  }
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

function openMergeSelectedDocuments() {
  if (selectedFiles.value.length < 2) {
    ElMessage.warning('请至少选择两个文档')
    return
  }
  if (!canMergeSelectedDocuments.value) {
    ElMessage.warning('只能合并文本、Markdown 或 HTML 文档')
    return
  }
  mergeDocumentForm.value = {
    target_name: '合并文档.md',
    target_format: 'markdown'
  }
  mergeDocumentVisible.value = true
}

function handleSelectionChange(selection: FileInfo[]) {
  if (syncingTableSelection.value) {
    return
  }
  selectedFiles.value = selection
}

async function exportSelectedFiles() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请先选择要导出的文件')
    return
  }

  exportFilesLoading.value = true
  try {
    const response = await filesApi.exportFiles(
      selectedFiles.value.map((file) => file.file_id),
      settingsStore.showHiddenContent
    )
    const fallbackName =
      selectedFiles.value.length === 1 ? selectedFiles.value[0].original_name : 'pfmt-export.zip'
    saveBlobResponse(response, fallbackName)
    ElMessage.success(selectedFiles.value.length === 1 ? '文件已开始导出' : '压缩包已开始导出')
  } finally {
    exportFilesLoading.value = false
  }
}

async function exportSingleFile(file: FileInfo) {
  const response = await filesApi.exportFile(file.file_id, settingsStore.showHiddenContent)
  saveBlobResponse(response, file.original_name)
  ElMessage.success('文件已开始导出')
}

async function mergeSelectedDocuments() {
  if (!canMergeSelectedDocuments.value) {
    ElMessage.warning('请至少选择两个文档')
    return
  }

  mergeDocumentLoading.value = true
  try {
    const merged = await filesApi.mergeDocuments(
      {
        file_ids: selectedFiles.value.map((file) => file.file_id),
        target_format: mergeDocumentForm.value.target_format,
        target_name: normalizeOptionalText(mergeDocumentForm.value.target_name)
      },
      settingsStore.showHiddenContent
    )
    mergeDocumentVisible.value = false
    selectedFiles.value = []
    ElMessage.success('已生成合并文档')
    await loadFiles()
    void router.push({
      name: 'document',
      params: {
        fileId: merged.file_id
      },
      query: {
        pathId: merged.path_id
      }
    })
  } finally {
    mergeDocumentLoading.value = false
  }
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
    const activeIds = new Set(files.value.map((file) => file.file_id))
    selectedFiles.value = selectedFiles.value.filter((file) => activeIds.has(file.file_id))
    void nextTick(syncTableSelection)
  } catch {
    files.value = []
    selectedFiles.value = []
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

watch(
  [viewMode, filteredFiles],
  () => {
    void nextTick(syncTableSelection)
  },
  { flush: 'post' }
)

watch(fileActionsDrawerVisible, (visible) => {
  if (!visible) {
    activeActionFile.value = null
  }
})

onMounted(() => {
  mobileMediaQuery = window.matchMedia(MOBILE_QUERY)
  handleViewportChange(mobileMediaQuery)
  mobileMediaQuery.addEventListener('change', handleViewportChange)
})

onBeforeUnmount(() => {
  mobileMediaQuery?.removeEventListener('change', handleViewportChange)
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
        <template v-if="!isMobileViewport">
          <el-button :icon="FolderAdd" @click="openCreateFolder">新建目录</el-button>
          <el-button :icon="DocumentAdd" @click="openCreateDocument">新建文档</el-button>
        </template>
        <el-button type="primary" :icon="UploadFilled" @click="openUploadDialog">上传</el-button>
        <el-dropdown trigger="click" @command="handlePathAction">
          <el-button v-if="isMobileViewport" :icon="MoreFilled" circle aria-label="更多目录操作" />
          <el-button v-else :icon="Operation">
            目录操作
            <el-icon class="folder-view__dropdown-icon"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <template v-if="isMobileViewport">
                <el-dropdown-item command="create-folder" :icon="FolderAdd">新建目录</el-dropdown-item>
                <el-dropdown-item command="create-document" :icon="DocumentAdd">新建文档</el-dropdown-item>
              </template>
              <el-dropdown-item
                command="edit-path"
                :icon="Edit"
                :disabled="currentPathIsRoot"
                :divided="isMobileViewport"
              >
                编辑目录
              </el-dropdown-item>
              <el-dropdown-item command="move-path" :icon="Rank" :disabled="currentPathIsRoot">
                移动目录
              </el-dropdown-item>
              <el-dropdown-item command="delete-path" :icon="FolderDelete" :disabled="currentPathIsRoot" divided>
                删除目录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <section class="work-panel">
      <div class="panel-header">
        <h2>文件列表</h2>
        <div class="folder-view__toolbar">
          <el-input
            v-model="fileKeyword"
            clearable
            placeholder="筛选文件名、备注、摘要"
            class="folder-view__filter folder-view__filter--search"
          />
          <template v-if="!isMobileViewport">
            <el-select
              v-model="fileTypeFilter"
              multiple
              clearable
              collapse-tags
              placeholder="类型筛选"
              class="folder-view__filter"
            >
              <el-option v-for="option in fileTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <el-select
              v-model="tagFilter"
              multiple
              clearable
              collapse-tags
              placeholder="标签筛选"
              class="folder-view__filter"
            >
              <el-option v-for="tagName in tagOptions" :key="tagName" :label="tagName" :value="tagName" />
            </el-select>
            <el-button :icon="Rank" :disabled="!selectedFiles.length" @click="openMoveSelectedFiles">
              移动所选
            </el-button>
            <el-button :icon="Download" :disabled="!selectedFiles.length" :loading="exportFilesLoading" @click="exportSelectedFiles">
              导出所选
            </el-button>
            <el-button :icon="DocumentAdd" :disabled="!canMergeSelectedDocuments" @click="openMergeSelectedDocuments">
              合并文档
            </el-button>
          </template>
          <template v-else>
            <el-button :icon="Filter" @click="filterDrawerVisible = true">筛选</el-button>
            <el-button :icon="Operation" :disabled="!selectedFiles.length" @click="batchActionsDrawerVisible = true">
              已选 {{ selectedFiles.length }}
            </el-button>
          </template>
          <el-button v-if="isMobileViewport" :icon="Refresh" circle :loading="loading" aria-label="刷新文件列表" @click="loadFiles" />
          <el-button v-else :icon="Refresh" :loading="loading" @click="loadFiles">刷新</el-button>
          <el-segmented v-model="viewMode" :options="viewModeOptions" />
        </div>
      </div>
      <div v-loading="loading" class="panel-body">
        <el-table
          v-if="viewMode === 'list' && !isMobileViewport"
          ref="fileTableRef"
          :data="filteredFiles"
          class="folder-view__table"
          border
          row-key="file_id"
          empty-text="当前目录暂无文件"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="46" reserve-selection />
          <el-table-column label="文件名" min-width="280">
            <template #default="{ row }">
              <button
                class="folder-view__file-name"
                type="button"
                :aria-label="`查看${row.original_name}`"
                @click="openFileDetail(row)"
              >
                <strong>{{ row.original_name }}</strong>
                <small v-if="row.tags?.length">{{ tagNames(row) }}</small>
              </button>
            </template>
          </el-table-column>
          <el-table-column label="文件类型" width="120">
            <template #default="{ row }">{{ fileTypeText(row.file_type) }}</template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.updated_at ?? row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="84" fixed="right" align="center">
            <template #default="{ row }">
              <el-dropdown trigger="click" @command="handleFileAction(row, $event)">
                <el-button
                  class="folder-view__more-button"
                  text
                  circle
                  :icon="MoreFilled"
                  :aria-label="`${row.original_name}的更多操作`"
                />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="action in fileActionItems(row)"
                      :key="action.command"
                      :command="action.command"
                      :icon="action.icon"
                      :class="{ 'folder-view__danger-action': action.danger }"
                    >
                      {{ action.label }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        <div v-else-if="viewMode === 'list' && filteredFiles.length" class="folder-view__mobile-list" aria-label="手机端文件列表">
          <article
            v-for="file in filteredFiles"
            :key="file.file_id"
            class="file-row"
            :class="{ 'file-row--selected': isFileSelected(file) }"
          >
            <el-checkbox
              class="file-row__select"
              :model-value="isFileSelected(file)"
              :aria-label="`选择${file.original_name}`"
              @change="(value: string | number | boolean) => toggleGridFileSelection(file, Boolean(value))"
            />
            <button class="file-row__icon" type="button" :aria-label="`查看${file.original_name}`" @click="openFileDetail(file)">
              {{ fileTypeText(file.file_type).slice(0, 1) }}
            </button>
            <button class="file-row__content" type="button" :aria-label="`查看${file.original_name}`" @click="openFileDetail(file)">
              <span class="file-row__title">
                <strong>{{ file.original_name }}</strong>
                <el-tag v-if="settingsStore.showHiddenContent && file.is_hidden" size="small" type="warning">隐藏</el-tag>
              </span>
              <span class="file-row__meta">
                {{ fileTypeText(file.file_type) }} · {{ formatFileSize(file.size_bytes) }} ·
                {{ formatDateTime(file.updated_at ?? file.created_at) }}
              </span>
              <small v-if="file.remark || file.tags?.length">
                {{ file.remark || tagNames(file) }}
              </small>
            </button>
            <el-button
              class="file-row__more"
              text
              circle
              :icon="MoreFilled"
              :aria-label="`${file.original_name}的更多操作`"
              @click="openFileActions(file)"
            />
          </article>
        </div>
        <div v-else-if="filteredFiles.length" class="folder-view__grid" aria-label="图标视图文件列表">
          <article
            v-for="file in filteredFiles"
            :key="file.file_id"
            class="file-card"
            :class="{ 'file-card--selected': isFileSelected(file) }"
            @dblclick="openFileDetail(file)"
          >
            <div class="file-card__top">
              <el-checkbox
                :model-value="isFileSelected(file)"
                :aria-label="`选择${file.original_name}`"
                @change="(value: string | number | boolean) => toggleGridFileSelection(file, Boolean(value))"
              />
              <el-tag v-if="settingsStore.showHiddenContent && file.is_hidden" class="file-card__hidden-tag" size="small" type="warning">
                隐藏
              </el-tag>
              <el-button
                v-if="isMobileViewport"
                class="file-card__more"
                text
                circle
                :icon="MoreFilled"
                :aria-label="`${file.original_name}的更多操作`"
                @click="openFileActions(file)"
              />
              <el-dropdown v-else trigger="click" @command="handleFileAction(file, $event)">
                <el-button
                  class="file-card__more"
                  text
                  circle
                  :icon="MoreFilled"
                  :aria-label="`${file.original_name}的更多操作`"
                />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="action in fileActionItems(file)"
                      :key="action.command"
                      :command="action.command"
                      :icon="action.icon"
                      :class="{ 'folder-view__danger-action': action.danger }"
                    >
                      {{ action.label }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <button class="file-card__main" type="button" :aria-label="`查看${file.original_name}`" @click="openFileDetail(file)">
              <span class="file-card__icon">{{ fileTypeText(file.file_type).slice(0, 1) }}</span>
              <strong>{{ file.original_name }}</strong>
              <small>{{ fileTypeText(file.file_type) }} · {{ formatFileSize(file.size_bytes) }}</small>
              <small v-if="file.tags?.length">{{ tagNames(file) }}</small>
            </button>
          </article>
        </div>
        <el-empty v-else description="当前目录暂无文件" />
      </div>
    </section>

    <el-drawer v-model="filterDrawerVisible" title="筛选文件" direction="btt" size="min(72vh, 420px)" class="folder-view__drawer">
      <div class="folder-view__drawer-form">
        <el-form label-position="top">
          <el-form-item label="文件类型">
            <el-select v-model="fileTypeFilter" multiple clearable collapse-tags placeholder="类型筛选" class="folder-view__path-select">
              <el-option v-for="option in fileTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="标签">
            <el-select v-model="tagFilter" multiple clearable collapse-tags placeholder="标签筛选" class="folder-view__path-select">
              <el-option v-for="tagName in tagOptions" :key="tagName" :label="tagName" :value="tagName" />
            </el-select>
          </el-form-item>
        </el-form>
        <div class="folder-view__drawer-footer">
          <el-button @click="clearFilters">清空筛选</el-button>
          <el-button type="primary" @click="filterDrawerVisible = false">完成</el-button>
        </div>
      </div>
    </el-drawer>

    <el-drawer
      v-model="batchActionsDrawerVisible"
      title="所选文件操作"
      direction="btt"
      size="min(72vh, 380px)"
      class="folder-view__drawer"
    >
      <div class="folder-view__sheet">
        <p class="folder-view__sheet-summary">已选择 {{ selectedFiles.length }} 个文件</p>
        <el-button :icon="Rank" :disabled="!selectedFiles.length" @click="openMoveSelectedFilesFromDrawer">移动所选</el-button>
        <el-button
          :icon="Download"
          :disabled="!selectedFiles.length"
          :loading="exportFilesLoading"
          @click="exportSelectedFilesFromDrawer"
        >
          导出所选
        </el-button>
        <el-button :icon="DocumentAdd" :disabled="!canMergeSelectedDocuments" @click="openMergeSelectedDocumentsFromDrawer">
          合并文档
        </el-button>
      </div>
    </el-drawer>

    <el-drawer
      v-model="fileActionsDrawerVisible"
      :title="activeActionFile?.original_name || '文件操作'"
      direction="btt"
      size="min(72vh, 360px)"
      class="folder-view__drawer"
    >
      <div class="folder-view__sheet">
        <button
          v-for="action in activeFileActions"
          :key="action.command"
          type="button"
          class="folder-view__sheet-action"
          :class="{ 'folder-view__sheet-action--danger': action.danger }"
          @click="handleActiveFileAction(action.command)"
        >
          <el-icon><component :is="action.icon" /></el-icon>
          <span>{{ action.label }}</span>
        </button>
      </div>
    </el-drawer>

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

    <el-dialog v-model="createDocumentVisible" title="新建文档" width="460px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="文档格式">
          <el-select :model-value="createDocumentForm.document_format" @change="handleCreateDocumentFormatChange">
            <el-option label="Markdown" value="markdown" />
            <el-option label="纯文本" value="plain_text" />
            <el-option label="HTML" value="html" />
          </el-select>
        </el-form-item>
        <el-form-item label="文档名称">
          <el-input v-model="createDocumentForm.original_name" maxlength="512" show-word-limit autofocus />
        </el-form-item>
        <el-form-item label="隐藏文档">
          <el-switch v-model="createDocumentForm.is_hidden" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDocumentVisible = false">取消</el-button>
        <el-button type="primary" :loading="createDocumentLoading" @click="createDocument">创建并打开</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="mergeDocumentVisible" title="合并为新文档" width="460px">
      <el-form label-position="top">
        <el-form-item label="已选文档">
          <span class="muted">{{ selectedDocumentFiles.length }} 个文档，将按原始文件名升序合并</span>
        </el-form-item>
        <el-form-item label="目标格式">
          <el-select v-model="mergeDocumentForm.target_format">
            <el-option label="Markdown" value="markdown" />
            <el-option label="纯文本" value="plain_text" />
            <el-option label="HTML" value="html" />
          </el-select>
        </el-form-item>
        <el-form-item label="新文件名">
          <el-input v-model="mergeDocumentForm.target_name" maxlength="512" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mergeDocumentVisible = false">取消</el-button>
        <el-button type="primary" :loading="mergeDocumentLoading" @click="mergeSelectedDocuments">
          生成合并文档
        </el-button>
      </template>
    </el-dialog>

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

.folder-view__dropdown-icon {
  margin-left: 4px;
}

.folder-view__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.folder-view__filter {
  width: 210px;
}

.folder-view__filter--search {
  width: 260px;
}

.folder-view__table :deep(.el-table__cell) {
  vertical-align: middle;
}

.folder-view__file-name {
  display: grid;
  width: 100%;
  gap: 4px;
  min-width: 0;
  padding: 0;
  color: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.folder-view__file-name:hover strong {
  color: var(--pfmt-primary);
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

.folder-view__more-button {
  width: 36px;
  height: 36px;
}

.folder-view__mobile-list {
  display: grid;
  gap: 10px;
}

.file-row {
  display: grid;
  min-width: 0;
  grid-template-columns: 32px 42px minmax(0, 1fr) 40px;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: #fff;
  border: 1px solid var(--pfmt-border-soft);
  border-radius: 8px;
}

.file-row--selected {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgb(64 158 255 / 12%);
}

.file-row__select {
  display: grid;
  width: 32px;
  height: 40px;
  align-items: center;
  justify-items: center;
}

.file-row__icon {
  display: grid;
  width: 42px;
  height: 42px;
  align-items: center;
  justify-items: center;
  color: #1f2937;
  background: #f3f6fb;
  border: 1px solid var(--pfmt-border);
  border-radius: 8px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

.file-row__content {
  display: grid;
  min-width: 0;
  gap: 4px;
  padding: 0;
  color: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.file-row__title {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 6px;
}

.file-row__title strong {
  display: -webkit-box;
  min-width: 0;
  overflow: hidden;
  line-height: 1.35;
  text-overflow: ellipsis;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.file-row__title .el-tag {
  flex: 0 0 auto;
}

.file-row__meta,
.file-row__content small {
  min-width: 0;
  overflow: hidden;
  color: var(--pfmt-text-muted);
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-row__more {
  width: 40px;
  height: 40px;
}

.folder-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 12px;
}

.file-card {
  display: grid;
  min-width: 0;
  min-height: 210px;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 8px;
  padding: 12px;
  background: #fff;
  border: 1px solid var(--pfmt-border);
  border-radius: 8px;
}

.file-card--selected {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgb(64 158 255 / 14%);
}

.file-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.file-card__hidden-tag {
  margin-left: auto;
}

.file-card__more {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
}

.file-card__main {
  display: grid;
  min-width: 0;
  align-content: center;
  justify-items: center;
  gap: 8px;
  padding: 8px;
  color: inherit;
  text-align: center;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.file-card__main:disabled {
  cursor: default;
}

.file-card__icon {
  display: grid;
  width: 54px;
  height: 54px;
  align-items: center;
  justify-items: center;
  color: #1f2937;
  background: #f3f6fb;
  border: 1px solid var(--pfmt-border);
  border-radius: 8px;
  font-size: 22px;
  font-weight: 700;
}

.file-card__main strong,
.file-card__main small {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-card__main small {
  color: var(--pfmt-text-muted);
}

.folder-view__path-select {
  width: 100%;
}

.folder-view__drawer :deep(.el-drawer__body) {
  padding-top: 0;
}

.folder-view__drawer-form {
  display: grid;
  gap: 10px;
}

.folder-view__drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.folder-view__sheet {
  display: grid;
  gap: 10px;
}

.folder-view__sheet-summary {
  margin: 0 0 4px;
  color: var(--pfmt-text-muted);
  line-height: 1.5;
}

.folder-view__sheet > .el-button {
  justify-content: flex-start;
  width: 100%;
  min-height: 42px;
  margin-left: 0;
}

.folder-view__sheet-action {
  display: grid;
  width: 100%;
  min-height: 44px;
  grid-template-columns: 22px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  padding: 0 4px;
  color: var(--pfmt-text);
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.folder-view__sheet-action span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-view__sheet-action--danger,
.folder-view__danger-action {
  color: var(--pfmt-danger);
}

@media (max-width: 820px) {
  .folder-view__actions {
    align-items: center;
    justify-content: flex-start;
    margin-top: 12px;
  }

  .folder-view :deep(.panel-header) {
    display: grid;
    gap: 12px;
    padding: 14px;
  }

  .folder-view__toolbar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    justify-content: stretch;
    gap: 8px;
  }

  .folder-view__filter--search,
  .folder-view__toolbar .el-segmented {
    grid-column: 1 / -1;
    width: 100%;
  }

  .folder-view__toolbar > .el-button {
    min-width: 40px;
  }

  .folder-view :deep(.panel-body) {
    padding: 12px;
  }

  .folder-view__grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
  }

  .file-card {
    min-height: 190px;
    padding: 10px;
  }
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
