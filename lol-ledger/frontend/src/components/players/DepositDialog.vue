<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="440px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div v-if="player" class="who">
      <div class="who-row">
        <span class="name">{{ player.game_id }}</span>
        <DepositBadge
          :cents="player.balance_cents"
          :deposit-cents="player.deposit_cents"
          :bonus-cents="player.bonus_cents"
          :level="player.deposit_level"
        />
      </div>
      <div class="who-meta">
        <span>现金押金 ¥{{ formatCents(player.deposit_cents) }}</span>
        <span>赠金 ¥{{ formatCents(player.bonus_cents) }}</span>
      </div>
    </div>

    <div v-if="blocked" class="blocked-tip">
      该玩家还有赠金 ¥{{ formatCents(player?.bonus_cents || 0) }}，赠金不能退。
      请先用赠金扣茶水，赠金为 0 后再退押金。
    </div>

    <el-form label-width="76px" class="form">
      <el-form-item label="金额">
        <el-input v-model="amount" placeholder="0.00" autocomplete="off" :disabled="blocked">
          <template #prefix>¥</template>
        </el-input>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="note" placeholder="可选" maxlength="200" :disabled="blocked" />
      </el-form-item>
    </el-form>

    <div v-if="mode === 'add'" class="campaign-line">
      <span v-if="campaignLoading" class="muted">正在读取充值活动…</span>
      <span v-else-if="campaignError" class="warn">
        活动信息读取失败，本笔赠送金额以提交后的结果为准
      </span>
      <span v-else-if="matchedCampaign">
        充值活动：满 ¥{{ formatCents(matchedCampaign.threshold_cents) }} 送
        ¥{{ formatCents(matchedCampaign.bonus_cents) }}，本笔自动赠送
        ¥{{ formatCents(matchedCampaign.bonus_cents) }}
      </span>
      <span v-else-if="campaigns.length && parsed !== null" class="muted">
        本笔未达到充值活动门槛
      </span>
    </div>

    <div class="preview">
      <span v-if="error" class="error">{{ error }}</span>
      <span v-else-if="after !== null">
        {{ previewLabel }}
        <b :class="after < 0 ? 'negative' : ''">{{ formatBalance(after, afterBonus, afterDeposit) }}</b>
        <span v-if="after < 0" class="negative-hint">（会变成负数）</span>
      </span>
      <span v-else class="muted">{{ hint }}</span>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="blocked || Boolean(error)"
        @click="submit"
      >
        确认
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { campaignApi, moneyApi } from '@/api'
import type { PlayerRow, RechargeCampaign } from '@/api/types'
import DepositBadge from '@/components/common/DepositBadge.vue'
import { formatBalance, formatCents, parseYuan } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
  player: PlayerRow | null
  mode: 'add' | 'refund' | 'bonus'
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved', value: PlayerRow): void
}>()

const amount = ref('')
const note = ref('')
const saving = ref(false)
const campaigns = ref<RechargeCampaign[]>([])
const campaignLoading = ref(false)
const campaignError = ref(false)

const title = computed(() => {
  if (props.mode === 'add') return '加押金'
  if (props.mode === 'refund') return '退押金'
  return '加赠金'
})

const hint = computed(() => {
  if (props.mode === 'add') return '金额必须大于 0，达到活动档位会自动送赠金'
  if (props.mode === 'refund') return '不能超过当前现金押金'
  return '赠金只能用于扣茶水，不能退款或划押'
})

const parsed = computed(() => parseYuan(amount.value))

const matchedCampaign = computed(() => {
  if (props.mode !== 'add' || parsed.value === null) return null
  const matched = campaigns.value
    .filter((item) => item.threshold_cents <= parsed.value!)
    .sort((a, b) => b.threshold_cents - a.threshold_cents)
  return matched[0] || null
})

const estimatedBonus = computed(() =>
  props.mode === 'add' ? matchedCampaign.value?.bonus_cents || 0 : 0,
)

const blocked = computed(
  () => props.mode === 'refund' && (props.player?.bonus_cents || 0) > 0,
)

const after = computed(() => {
  if (parsed.value === null || !props.player) return null
  if (props.mode === 'add') {
    return props.player.balance_cents + parsed.value + estimatedBonus.value
  }
  if (props.mode === 'refund') {
    return props.player.deposit_cents - parsed.value
  }
  return props.player.balance_cents + parsed.value
})

const afterDeposit = computed(() => {
  if (parsed.value === null || !props.player) return 0
  if (props.mode === 'add') return props.player.deposit_cents + parsed.value
  if (props.mode === 'refund') return props.player.deposit_cents - parsed.value
  return props.player.deposit_cents
})

const afterBonus = computed(() => {
  if (parsed.value === null || !props.player) return 0
  if (props.mode === 'add') return props.player.bonus_cents + estimatedBonus.value
  if (props.mode === 'refund') return props.player.bonus_cents
  return props.player.bonus_cents + parsed.value
})

const previewLabel = computed(() =>
  props.mode === 'bonus' ? '变动后余额' : '变动后余额',
)

const error = computed(() => {
  if (blocked.value) {
    return `该玩家还有赠金 ¥${formatCents(props.player?.bonus_cents || 0)}，不能退押金`
  }
  if (!amount.value.trim()) return ''
  if (parsed.value === null) return '金额格式不正确，最多两位小数'
  if (parsed.value <= 0) return `${title.value}金额必须大于 0`
  if (
    props.mode === 'refund' &&
    props.player &&
    parsed.value > props.player.deposit_cents
  ) {
    return '现金押金不足，不能退这么多'
  }
  return ''
})

async function loadCampaigns() {
  if (props.mode !== 'add') return
  campaignLoading.value = true
  campaignError.value = false
  try {
    campaigns.value = await campaignApi.list()
  } catch {
    campaigns.value = []
    campaignError.value = true
  } finally {
    campaignLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    note.value = ''
    campaignError.value = false
    campaigns.value = []
    if (
      props.mode === 'refund' &&
      props.player &&
      props.player.deposit_cents > 0 &&
      props.player.bonus_cents === 0
    ) {
      amount.value = formatCents(props.player.deposit_cents)
    } else {
      amount.value = ''
    }
    void loadCampaigns()
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
  if (!props.player) return

  saving.value = true
  try {
    const playerId = props.player.id
    if (props.mode === 'add') {
      const result = await moneyApi.addDeposit(playerId, cents, note.value.trim())
      ElMessage.success(
        result.bonus_entry
          ? `加押金成功，自动赠送 ¥${formatCents(result.bonus_entry.amount_cents)}`
          : '加押金成功',
      )
      emit('saved', result.player)
    } else if (props.mode === 'refund') {
      const result = await moneyApi.refund(playerId, cents, note.value.trim())
      ElMessage.success('退押金成功')
      emit('saved', result.player)
    } else {
      const result = await moneyApi.addBonus(playerId, cents, note.value.trim())
      ElMessage.success('加赠金成功')
      emit('saved', result.player)
    }
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.who {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  margin-bottom: 16px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border-strong);
  border-radius: 8px;
}

.who-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.who-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.name {
  font-weight: 600;
  font-size: 14px;
}

.blocked-tip {
  margin-bottom: 14px;
  padding: 9px 11px;
  border: 1px solid rgba(230, 162, 60, 0.32);
  background: var(--app-warning-soft);
  border-radius: 7px;
  font-size: 12px;
  color: var(--el-color-warning);
  line-height: 1.6;
}

.form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.campaign-line {
  min-height: 18px;
  padding-left: 76px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--el-color-primary);
  line-height: 1.5;
}

.preview {
  min-height: 20px;
  padding-left: 76px;
  font-size: 12.5px;
  color: var(--el-text-color-regular);
}

.error,
.warn {
  color: var(--el-color-danger);
}

.warn {
  color: var(--el-color-warning);
}

.negative {
  color: var(--el-color-danger);
  font-weight: 600;
}

.negative-hint {
  color: var(--el-color-danger);
  margin-left: 4px;
}
</style>
