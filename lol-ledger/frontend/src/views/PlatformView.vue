<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">平台管理</span>
      <span class="page-sub">商家账号 · 查战绩配额</span>
    </div>

    <el-tabs v-model="tab" class="platform-tabs">
      <el-tab-pane label="商家与账号" name="merchants" lazy>
        <MerchantPanel />
      </el-tab-pane>
      <el-tab-pane label="查战绩配额" name="zj" lazy>
        <ZhanjiQuotaPanel />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import MerchantPanel from '@/views/platform/MerchantPanel.vue'
import ZhanjiQuotaPanel from '@/views/platform/ZhanjiQuotaPanel.vue'

const tab = ref<'merchants' | 'zj'>('merchants')
</script>

<style scoped>
.platform-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.platform-tabs :deep(.el-tabs__item) {
  font-size: 13.5px;
}
</style>
