<template>
  <div class="shell">
    <TopBar />
    <main class="shell-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import TopBar from '@/layouts/TopBar.vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()
onMounted(() => app.applyTheme())
</script>

<style scoped>
.shell {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color-page);
}

.shell-main {
  flex: 1;
}
</style>
