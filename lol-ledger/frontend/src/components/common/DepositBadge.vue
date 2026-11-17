<template>
  <span class="badge" :class="[level, { negative: cents < 0 }]">
    {{ formatCents(cents) }}<span v-if="bonusCents > 0" class="cash-hint">
      （押金 {{ formatCents(depositCents) }}）
    </span>
  </span>
</template>

<script setup lang="ts">
import { formatCents } from '@/utils/money'

withDefaults(
  defineProps<{
    cents: number
    depositCents?: number
    bonusCents?: number
    level: 'low' | 'warn' | 'safe' | string
  }>(),
  { depositCents: 0, bonusCents: 0 },
)
</script>

<style scoped>
.badge {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  font-size: 13.5px;
}

.badge.low {
  color: var(--el-text-color-primary);
}

.badge.warn {
  color: var(--el-color-warning);
}

.badge.safe {
  color: var(--el-color-success);
}

.badge.negative {
  color: var(--el-color-danger);
}

.cash-hint {
  margin-left: 3px;
  font-size: 11.5px;
  font-weight: 400;
  color: var(--app-text-muted);
}
</style>
