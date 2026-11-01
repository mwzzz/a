<template>
  <span class="amount" :class="tone">{{ text }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { formatCents, formatChange } from '@/utils/money'

const props = withDefaults(
  defineProps<{
    cents: number
    change?: boolean
    colorful?: boolean
  }>(),
  { change: false, colorful: true },
)

const text = computed(() =>
  props.change ? formatChange(props.cents) : formatCents(props.cents),
)

const tone = computed(() => {
  if (!props.colorful) return ''
  if (props.cents > 0) return 'in'
  if (props.cents < 0) return 'out'
  return 'zero'
})
</script>

<style scoped>
.zero {
  color: var(--el-text-color-secondary);
}
</style>
