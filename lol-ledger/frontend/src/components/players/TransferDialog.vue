<template>
  <el-dialog
    :model-value="modelValue"
    title="划押"
    width="470px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div v-if="player" class="who">
      <div class="line">
        <span class="muted">从</span>
        <span class="name">{{ player.game_id }}</span>
        <span class="muted">划转押金给其他玩家</span>
      </div>
      <div class="balance">
        <span class="muted">当前押金</span>
        <DepositBadge :cents="player.deposit_cents" :level="player.deposit_level" />
      </div>
    </div>

    <el-form label-width="92px">
      <el-form-item label="目标玩家" required>
        <PlayerSelect v-model="target" :exclude-ids="player ? [player.id] : []" />
      </el-form-item>
      <el-form-item label="划转金额" required>
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
      <span v-else-if="after !== null" :class="after < 0 ? 'error' : 'muted'">
        划出后押金 ¥{{ formatCents(after) }}
      </span>
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
import PlayerSelect from '@/components/common/PlayerSelect.vue'
import { formatCents, parseYuan } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
  player: PlayerRow | null
  defaultAmountCents: number
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved'): void
}>()

const target = ref<number | null>(null)
const amount = ref('')
const note = ref('')
const saving = ref(false)

const parsed = computed(() => parseYuan(amount.value))
const after = computed(() => {
  if (parsed.value === null || !props.player) return null
  return props.player.deposit_cents - parsed.value
})

const error = computed(() => {
  if (!amount.value.trim()) return ''
  if (parsed.value === null) return '金额格式不正确，最多两位小数'
  if (parsed.value <= 0) return '划转金额必须大于 0'
  return ''
})

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    target.value = null
    note.value = ''
    amount.value = props.defaultAmountCents > 0 ? formatCents(props.defaultAmountCents) : ''
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  if (!target.value) {
    ElMessage.warning('请选择目标玩家')
    return
  }
  const cents = parsed.value
  if (cents === null || cents <= 0) {
    ElMessage.warning('请输入正确的划转金额')
    return
  }
  if (!props.player) return

  if (after.value !== null && after.value < 0) {
    try {
      await ElMessageBox.confirm(
        `划转后押金会变成 ¥${formatCents(after.value)}，确定继续？`,
        '请确认',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }

  saving.value = true
  try {
    await moneyApi.transfer(props.player.id, target.value, cents, note.value.trim())
    ElMessage.success('划押成功')
    emit('saved')
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
  justify-content: space-between;
  gap: 12px;
  padding: 11px 13px;
  margin-bottom: 16px;
  background: #101319;
  border: 1px solid #232833;
  border-radius: 8px;
}

.line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.name {
  font-weight: 600;
}

.balance {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.preview {
  min-height: 20px;
  padding-left: 92px;
  font-size: 12.5px;
}

.error {
  color: var(--el-color-danger);
}
</style>
