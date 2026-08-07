<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowLeft, Close, ZoomIn, ZoomOut } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  title: string
  imageUrl: string
  loading?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const scale = ref(1)
const panX = ref(0)
const panY = ref(0)
const panning = ref(false)
const panStart = ref({ x: 0, y: 0, panX: 0, panY: 0 })

const imageTransform = computed(() => `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`)

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      resetZoom()
    }
  }
)

function close() {
  emit('update:modelValue', false)
}

function zoomImage(delta: number) {
  const nextScale = Math.min(4, Math.max(0.25, scale.value + delta))
  scale.value = Number(nextScale.toFixed(2))
  if (scale.value <= 1) {
    panX.value = 0
    panY.value = 0
  }
}

function resetZoom() {
  scale.value = 1
  panX.value = 0
  panY.value = 0
  panning.value = false
}

function startPan(event: PointerEvent) {
  if (scale.value <= 1) {
    return
  }
  panning.value = true
  panStart.value = {
    x: event.clientX,
    y: event.clientY,
    panX: panX.value,
    panY: panY.value
  }
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
}

function movePan(event: PointerEvent) {
  if (!panning.value) {
    return
  }
  panX.value = panStart.value.panX + event.clientX - panStart.value.x
  panY.value = panStart.value.panY + event.clientY - panStart.value.y
}

function stopPan(event?: PointerEvent) {
  panning.value = false
  if (event?.currentTarget instanceof HTMLElement) {
    try {
      event.currentTarget.releasePointerCapture(event.pointerId)
    } catch {
      // Pointer capture may already be released when the cursor leaves the image.
    }
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="document-image-preview">
      <div class="document-image-preview__topbar">
        <div class="document-image-preview__title">
          <el-icon><ArrowLeft /></el-icon>
          <strong>{{ title }}</strong>
        </div>
        <div class="document-image-preview__tools">
          <el-button circle plain :icon="ZoomOut" :disabled="scale <= 0.25" @click="zoomImage(-0.25)" />
          <span class="document-image-preview__scale">{{ Math.round(scale * 100) }}%</span>
          <el-button circle plain :icon="ZoomIn" :disabled="scale >= 4" @click="zoomImage(0.25)" />
          <el-button plain @click="resetZoom">适应窗口</el-button>
          <el-button circle plain :icon="Close" @click="close" />
        </div>
      </div>

      <div v-loading="loading" class="document-image-preview__stage" @click.self="close">
        <img
          v-if="imageUrl"
          class="document-image-preview__image"
          :class="{
            'document-image-preview__image--zoomed': scale > 1,
            'document-image-preview__image--panning': panning
          }"
          :src="imageUrl"
          :alt="title"
          :style="{ transform: imageTransform }"
          draggable="false"
          @pointerdown.prevent="startPan"
          @pointermove.prevent="movePan"
          @pointerup="stopPan"
          @pointercancel="stopPan"
          @lostpointercapture="stopPan"
        />
        <el-empty v-else-if="!loading" description="图片加载失败" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.document-image-preview {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  background: rgba(12, 18, 28, 0.9);
}

.document-image-preview__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  color: #fff;
  background: rgba(15, 23, 42, 0.78);
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}

.document-image-preview__title {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.document-image-preview__title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-image-preview__tools {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.document-image-preview__scale {
  min-width: 48px;
  text-align: center;
  color: #dbeafe;
  font-size: 13px;
}

.document-image-preview__stage {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  overflow: hidden;
  padding: 20px;
}

.document-image-preview__image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
  transition: transform 0.12s ease;
  cursor: zoom-in;
}

.document-image-preview__image--zoomed {
  cursor: grab;
}

.document-image-preview__image--panning {
  cursor: grabbing;
  transition: none;
}

@media (max-width: 720px) {
  .document-image-preview__topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .document-image-preview__tools {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
