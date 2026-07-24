<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

onMounted(() => {
  const fileId = route.params.fileId
  if (typeof fileId === 'string' && fileId) {
    void router.replace({
      name: 'file-detail',
      params: {
        fileId
      },
      query: route.query
    })
    return
  }

  void router.replace({
    name: 'folder',
    params: {
      pathId: 'root'
    }
  })
})
</script>

<template>
  <section class="page-shell markdown-redirect">
    <el-empty description="正在打开文件详情" />
  </section>
</template>

<style scoped>
.markdown-redirect {
  display: grid;
  min-height: 360px;
  place-items: center;
}
</style>
