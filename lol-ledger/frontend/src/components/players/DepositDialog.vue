<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="430px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div v-if="player" class="who">
      <span class="name">{{ player.game_id }}</span>
      <span class="muted">当前押金</span>
      <DepositBadge :cents="player.deposit_cents" :level="player.deposit_level" />
    </div>

    <el-form label-width="76px" class="form">
      <el-form-item label="金额">
        <el-input v-model="amount" placeholder="0.00" autocomplete="off">
          <template #prefix>¥</template>
        </el-input>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="note" placeholder="可选" maxlength="200" />
      </el-form-item>
    </el-form>
    <div class="preview">
      <span v-if="error" class="error">{{ error }}</span>
      <span v-else-if="afterCents !== null">
        变动后押金
        <b :class="afterCents < 0 ? 'neg' : ''">¥{{ formatCents(afterCents) }}</b>
        <span v-if="afterCents < 0" class="neg-hint">（会变成负数）</span>
      </span>
      <span v-else class="muted">{{ hint }}</span>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="Boolean(error)" @click="submit">
        确认
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { moneyApi } from '@/api'
import type { PlayerRow } from '@/api/types'
import DepositBadge from '@/components/common/DepositBadge.vue'
import { formatCents, parseYuan } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
  player: PlayerRow | null
  mode: 'add' | 'refund' | 'deduct'
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved', value: PlayerRow): void
}>()

const amount = ref('')
const note = ref('')
const saving = ref(false)

const title = computed(() => {
  if (props.mode === 'add') return '加押金'
  if (props.mode === 'refund') return '退押金'
  return '扣押金'
})

const hint = computed(() => {
  if (props.mode === 'refund') return '不能超过当前押金'
  if (props.mode === 'deduct') return '可以扣成负数'
  return '金额必须大于 0'
})

const parsed = computed(() => parseYuan(amount.value))

const afterCents = computed(() => {
  if (parsed.value === null || !props.player) return null
  return props.mode === 'add'
    ? props.player.deposit_cents + parsed.value
    : props.player.deposit_cents - parsed.value
})

const error = computed(() => {
  if (!amount.value.trim()) return ''
  if (parsed.value === null) return '金额格式不正确，最多两位小数'
  if (props.mode === 'add' && parsed.value <= 0) return '加押金金额必须大于 0'
  if (props.mode === 'refund') {
    if (parsed.value <= 0) return '退押金金额必须大于 0'
    if (props.player && parsed.value > props.player.deposit_cents) return '押金不足，不能退这么多'
  }
  return ''
})

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    note.value = ''
    if (props.mode === 'refund' && props.player && props.player.deposit_cents > 0) {
      amount.value = formatCents(props.player.deposit_cents)
    } else {
      amount.value = ''
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  const cents = parsed.value
  if (cents === null) {
    ElMessage.warning('请输入正确的金额')
    return
  }
  if (error.value) {
    ElMessage.warning(error.value)
    return
  }
  if (props.mode === 'deduct' && afterCents.value !== null && afterCents.value < 0) {
    try {
      await ElMessageBox.confirm(
        `扣押后押金会变成 ¥${formatCents(afterCents.value)}，确定继续？`,
        '请确认',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }
  if (!props.player) return

  saving.value = true
  try {
    const playerId = props.player.id
    const value = props.mode === 'add'
      ? await moneyApi.addDeposit(playerId, cents, note.value.trim())
      : props.mode === 'refund'
        ? await moneyApi.refund(playerId, cents, note.value.trim())
        : await moneyApi.deduct(playerId, cents, note.value.trim())
    ElMessage.success(`${title.value}成功`)
    emit('saved', value.player)
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.who {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 16px;
  background: #101319;
  border: 1px solid #232833;
  border-radius: 8px;
}

.name {
  font-weight: 600;
  font-size: 14px;
}

.form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.preview {
  min-height: 20px;
  padding-left: 76px;
  font-size: 12.5px;
  color: var(--el-text-color-regular);
}

.error {
  color: var(--el-color-danger);
}

.neg {
  color: var(--el-color-danger);
  font-weight: 600;
}

.neg-hint {
  color: var(--el-color-danger);
  margin-left: 4px;
}
</style>
