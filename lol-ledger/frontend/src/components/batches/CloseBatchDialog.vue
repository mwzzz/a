<template>
  <el-dialog
    :model-value="modelValue"
    title="交班"
    width="520px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div class="head">
      <span class="muted">即将结束</span>
      <b>{{ batch?.display_label }}</b>
    </div>

    <div v-loading="loading" class="stats">
      <div class="stat"><span>局数</span><b>{{ summary?.session_count ?? '-' }}</b></div>
      <div class="stat"><span>人次</span><b>{{ summary?.player_times ?? '-' }}</b></div>
      <div class="stat"><span>茶水合计</span><b>¥{{ formatCents(summary?.tea_total_cents ?? 0) }}</b></div>
      <div class="stat"><span>加押金</span><b>¥{{ formatCents(summary?.add_total_cents ?? 0) }}</b></div>
      <div class="stat"><span>退押金</span><b>¥{{ formatCents(summary?.refund_total_cents ?? 0) }}</b></div>
      <div class="stat"><span>手动扣押</span><b>¥{{ formatCents(summary?.deduct_total_cents ?? 0) }}</b></div>
      <div class="stat">
        <span>划转</span>
        <b>{{ summary?.transfer_count ?? 0 }} 笔 / ¥{{ formatCents(summary?.transfer_out_total_cents ?? 0) }}</b>
      </div>
      <div class="stat"><span>期末总押金</span><b>¥{{ formatCents(summary?.deposit_total_cents ?? 0) }}</b></div>
    </div>

    <div class="note">
      <label>交班备注</label>
      <el-input v-model="note" placeholder="可选，比如交给晚班" maxlength="200" />
    </div>

    <div class="tip">交班后这个批次不能再新增场次，汇总数字会保存成快照。</div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading" @click="submit">
        确认交班
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { ref, watch } from 'vue'

import { batchApi } from '@/api'
import type { BatchRow, BatchSummary } from '@/api/types'
import { formatCents } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
  batch: BatchRow | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'closed', value: BatchSummary): void
}>()

const summary = ref<BatchSummary | null>(null)
const note = ref('')
const loading = ref(false)
const saving = ref(false)

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible || !props.batch) return
    note.value = ''
    summary.value = null
    loading.value = true
    try {
      summary.value = await batchApi.summary(props.batch.id)
    } finally {
      loading.value = false
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  if (!props.batch) return
  saving.value = true
  try {
    const result = await batchApi.close(props.batch.id, note.value.trim())
    ElMessage.success(
      `已交班：${result.session_count} 局，茶水 ¥${formatCents(result.tea_total_cents)}，期末总押金 ¥${formatCents(result.deposit_total_cents)}`,
    )
    emit('closed', result)
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  font-size: 13px;
}

.stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 14px;
}

.stat {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  background: #101319;
  border: 1px solid #1e222b;
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}

.stat b {
  color: var(--el-text-color-primary);
  font-size: 13.5px;
  font-variant-numeric: tabular-nums;
}

.note {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.note label {
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}

.tip {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
}
</style>
