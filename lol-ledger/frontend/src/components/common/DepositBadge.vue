<template>
  <span class="badge" :class="level">{{ formatCents(cents) }}</span>
</template>

<script setup lang="ts">
import { formatCents } from '@/utils/money'

defineProps<{
  cents: number
  level: 'low' | 'warn' | 'safe' | string
}>()
</script>

<style scoped>
.badge {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  font-size: 13.5px;
}

.badge.low {
  color: var(--el-color-danger);
}

.badge.warn {
  color: var(--el-color-warning);
}

.badge.safe {
  color: var(--el-color-success);
}
</style>
