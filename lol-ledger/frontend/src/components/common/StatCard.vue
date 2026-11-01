<template>
  <div class="stat-card">
    <div class="label">{{ label }}</div>
    <div class="value" :class="tone">{{ value }}</div>
    <div v-if="hint" class="hint">{{ hint }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string
    hint?: string
    tone?: 'default' | 'good' | 'warn' | 'bad'
  }>(),
  { hint: '', tone: 'default' },
)
</script>

<style scoped>
.stat-card {
  flex: 1;
  min-width: 170px;
  padding: 15px 18px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
}

.label {
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}

.value {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.2px;
}

.value.good {
  color: var(--el-color-success);
}

.value.warn {
  color: var(--el-color-warning);
}

.value.bad {
  color: var(--el-color-danger);
}

.hint {
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
}
</style>
