<template>
  <div class="shell">
    <TopBar />
    <ShiftStrip />
    <main class="shell-main">
      <router-view />
    </main>
    <BottomNav />
    <NewSessionDialog
      v-model="app.sessionDialogVisible"
      @created="app.notifySessionCreated()"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import NewSessionDialog from '@/components/batches/NewSessionDialog.vue'
import BottomNav from '@/layouts/BottomNav.vue'
import ShiftStrip from '@/layouts/ShiftStrip.vue'
import TopBar from '@/layouts/TopBar.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const app = useAppStore()
const auth = useAuthStore()
onMounted(() => {
  app.applyTheme()
  if (!auth.isSuperadmin) void app.refreshToday()
})
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
  padding-bottom: 0;
}

@media (max-width: 768px) {
  .shell-main {
    padding-bottom: 64px;
  }
}
</style>
