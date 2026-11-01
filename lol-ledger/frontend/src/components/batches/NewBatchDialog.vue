<template>
  <el-dialog
    :model-value="modelValue"
    title="开班"
    width="400px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div class="tip">开班后这一班的所有场次和押金变动都会记在这个批次里，交班时统一对账。</div>
    <el-form label-width="70px">
      <el-form-item label="批次名">
        <el-input v-model="label" placeholder="留空自动用开班时间" maxlength="64" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="note" placeholder="可选，比如早班" maxlength="200" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">开班</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { ref, watch } from 'vue'

import { batchApi } from '@/api'
import type { BatchRow } from '@/api/types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created', value: BatchRow): void
}>()

const label = ref('')
const note = ref('')
const saving = ref(false)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    label.value = ''
    note.value = ''
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  saving.value = true
  try {
    const batch = await batchApi.create({ label: label.value.trim(), note: note.value.trim() })
    ElMessage.success('已开班')
    emit('created', batch)
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.tip {
  padding: 9px 12px;
  margin-bottom: 14px;
  background: #101319;
  border: 1px solid #1e222b;
  border-radius: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
</style>
