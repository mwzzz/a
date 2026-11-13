<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">报表</span>
      <span class="page-sub">流水明细与分红结算</span>
    </div>

    <el-tabs v-model="activeTab" class="report-tabs" @tab-change="onTabChange">
      <el-tab-pane label="流水明细" name="records">
        <RecordsView embedded />
      </el-tab-pane>
      <el-tab-pane v-if="auth.isAdmin" label="分红结算" name="dividend">
        <DividendSettlementView />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import DividendSettlementView from '@/views/DividendSettlementView.vue'
import RecordsView from '@/views/RecordsView.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

function validTabs(): string[] {
  return auth.isAdmin ? ['records', 'dividend'] : ['records']
}

function queryTab(): string {
  const tab = typeof route.query.tab === 'string' ? route.query.tab : ''
  return validTabs().includes(tab) ? tab : 'records'
}

const activeTab = ref(queryTab())

watch(
  () => route.query.tab,
  () => {
    activeTab.value = queryTab()
  },
)

function onTabChange(name: string | number) {
  router.replace({ query: { ...route.query, tab: String(name) } })
}
</script>

<style scoped>
.report-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .report-tabs :deep(.el-tabs__nav-wrap) {
    overflow-x: auto;
  }
}
</style>
