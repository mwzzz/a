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
  color: #ff5c5c;
}

.badge.warn {
  color: #f0b429;
}

.badge.safe {
  color: #3ecf8e;
}
</style>
