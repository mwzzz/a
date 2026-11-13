<template>
  <span class="status-tag" :class="`is-${type}`">
    <span class="status-dot"></span>
    <span>{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    type?: 'success' | 'warning' | 'danger' | 'info' | 'primary'
  }>(),
  { type: 'info' },
)
</script>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  color: var(--app-text-muted);
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  white-space: nowrap;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.is-success {
  color: var(--el-color-success);
  background: var(--app-success-soft);
  border-color: transparent;
}

.is-warning {
  color: var(--el-color-warning);
  background: var(--app-warning-soft);
  border-color: transparent;
}

.is-danger {
  color: var(--el-color-danger);
  background: var(--app-danger-soft);
  border-color: transparent;
}

.is-primary {
  color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.1);
  border-color: transparent;
}
</style>
