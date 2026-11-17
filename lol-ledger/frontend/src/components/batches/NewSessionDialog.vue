<template>
  <el-dialog
    :model-value="modelValue"
    title="新增场次"
    width="720px"
    top="6vh"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <AiPlayerRecognition
      :active="modelValue"
      :tea-free-keys="teaFreeKeys"
      :tea-fee-cents="teaCents"
      @apply="applyAiPlayers"
    />

    <div class="players-head">
      <span class="section-title">参与玩家</span>
      <span class="count" :class="{ full: filledCount === 10 }">{{ filledCount }}/10</span>
      <div class="spacer"></div>
      <span class="muted small">同一局不能重复选同一个人</span>
    </div>

    <div class="slots">
      <div v-for="(slot, index) in slots" :key="index" class="slot" :class="{ empty: !slot }">
        <span class="idx">#{{ index + 1 }}</span>
        <PlayerSelect
          v-model="slots[index]"
          :exclude-ids="otherSelected(index)"
          :tea-free-keys="teaFreeKeys"
          :placeholder="slot ? '已选择' : '+ 添加'"
        />
        <el-button v-if="slot" link type="info" class="clear" @click="slots[index] = null">
          清空
        </el-button>
      </div>
    </div>

    <div class="add-row">
      <PlayerSelect
        v-model="adding"
        :exclude-ids="selectedIds"
        :tea-free-keys="teaFreeKeys"
        placeholder="搜索并添加玩家"
      />
    </div>

    <div class="summary">
      <span>已选 <b>{{ filledCount }}</b> 人</span>
      <span>茶水合计 <b>¥{{ formatCents(teaTotalCents) }}</b></span>
      <span v-if="previewState === 'idle'" class="muted">选择玩家后自动校验押金</span>
      <span v-else-if="previewState === 'loading'" class="muted">正在校验押金…</span>
      <template v-else-if="previewState === 'error'">
        <span class="danger">押金校验失败，校验通过前不能创建</span>
        <el-button link type="primary" size="small" @click="retryPreview">重试</el-button>
      </template>
      <span v-else-if="previewState === 'negative'" class="danger">
        有 {{ preview?.negative_count }} 人会扣成负数：{{ preview?.negative_players?.join('、') }}
      </span>
      <span v-else class="muted">没有人的押金会被扣成负数</span>
      <span v-if="bonusDeductTotal > 0" class="muted">
        其中赠金抵扣 ¥{{ formatCents(bonusDeductTotal) }}
      </span>
      <span v-if="lowDepositPlayers.length" class="warn">
        押金不足 ¥{{ formatCents((teaCents || 0) * 11) }}（茶水×11）：{{ lowDepositPlayers.join('、') }}
      </span>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canCreate" @click="submit">
        创建
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { sessionApi, toolListApi } from '@/api'
import type { PreviewPayload } from '@/api/types'
import AiPlayerRecognition from '@/components/batches/AiPlayerRecognition.vue'
import PlayerSelect from '@/components/common/PlayerSelect.vue'
import { formatCents } from '@/utils/money'
import { nameKey } from '@/utils/names'

const props = defineProps<{
  modelValue: boolean
  defaultTeaCents: number
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created', value: Record<string, never>): void
}>()

type PreviewState = 'idle' | 'loading' | 'error' | 'safe' | 'negative'

const slots = ref<(number | null)[]>(Array(10).fill(null))
const adding = ref<number | null>(null)
const saving = ref(false)
const preview = ref<PreviewPayload | null>(null)
const previewLoading = ref(false)
const previewError = ref(false)
const teaFreeKeys = ref<string[]>([])

const filledIds = computed(() => slots.value.filter((item): item is number => Boolean(item)))
const filledCount = computed(() => filledIds.value.length)
const selectedIds = computed(() => filledIds.value)

const teaCents = computed(() =>
  Number.isFinite(props.defaultTeaCents) ? props.defaultTeaCents : 200,
)

const teaTotalCents = computed(() => teaCents.value * filledCount.value)

const bonusDeductTotal = computed(
  () =>
    preview.value?.items.reduce((sum, item) => sum + item.bonus_deduct_cents, 0) || 0,
)

const lowDepositPlayers = computed(() => {
  if (!preview.value || !teaCents.value) return []
  const threshold = teaCents.value * 11
  return preview.value.items
    .filter((item) => item.before_cents < threshold)
    .map((item) => item.game_id)
})

const previewState = computed<PreviewState>(() => {
  if (!filledCount.value) return 'idle'
  if (previewLoading.value) return 'loading'
  if (previewError.value || !preview.value) return 'error'
  return preview.value.negative_count > 0 ? 'negative' : 'safe'
})

const previewReady = computed(
  () => previewState.value === 'safe' || previewState.value === 'negative',
)
const canCreate = computed(
  () => filledCount.value > 0 && previewReady.value && !saving.value,
)

async function loadTeaFreePlayers() {
  try {
    const data = await toolListApi.list()
    const list = data.lists.find((item) => item.name === '免茶水')
    teaFreeKeys.value = (list?.items || [])
      .map((item) => nameKey(item.content))
      .filter(Boolean)
  } catch {
    teaFreeKeys.value = []
  }
}

function otherSelected(index: number): number[] {
  return slots.value.filter((item, position) => Boolean(item) && position !== index) as number[]
}

async function applyAiPlayers(ids: number[]) {
  const unique = [...new Set(ids)].slice(0, 10)
  if (!unique.length) return

  const existing = new Set(filledIds.value)
  const fresh = unique.filter((id) => !existing.has(id))
  if (!fresh.length) {
    ElMessage.info('识别到的人已经在场次里了')
    return
  }

  const emptySlots = slots.value
    .map((value, index) => (value === null ? index : -1))
    .filter((index) => index >= 0)

  if (fresh.length <= emptySlots.length) {
    fresh.forEach((id, position) => {
      slots.value[emptySlots[position]] = id
    })
    ElMessage.success(`已填入 ${fresh.length} 个玩家`)
    return
  }

  try {
    await ElMessageBox.confirm(
      `识别出 ${unique.length} 人，但当前只剩 ${emptySlots.length} 个空位，是否用识别结果覆盖已选玩家？`,
      '覆盖当前选择',
      { confirmButtonText: '覆盖', cancelButtonText: '不覆盖', type: 'warning' },
    )
  } catch {
    return
  }
  slots.value = Array(10).fill(null)
  unique.forEach((id, position) => {
    slots.value[position] = id
  })
  ElMessage.success(`已填入 ${unique.length} 个玩家`)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    resetPreviewState()
    slots.value = Array(10).fill(null)
    adding.value = null
    void loadTeaFreePlayers()
  },
)

watch(adding, (value) => {
  if (!value) return
  const index = slots.value.findIndex((item) => !item)
  if (index >= 0) {
    slots.value[index] = value
  } else {
    ElMessage.warning('已经选满 10 人')
  }
  adding.value = null
})

let previewTimer: number | undefined
let previewSeq = 0

function resetPreviewState() {
  previewSeq += 1
  window.clearTimeout(previewTimer)
  preview.value = null
  previewLoading.value = false
  previewError.value = false
}

async function runPreview(seq: number) {
  try {
    const payload = await sessionApi.preview(filledIds.value, teaCents.value)
    if (seq !== previewSeq) return
    preview.value = payload
  } catch {
    if (seq !== previewSeq) return
    preview.value = null
    previewError.value = true
  } finally {
    if (seq === previewSeq) previewLoading.value = false
  }
}

function schedulePreview(immediate = false) {
  window.clearTimeout(previewTimer)
  previewSeq += 1
  const seq = previewSeq
  preview.value = null
  previewError.value = false
  if (!filledCount.value) {
    previewLoading.value = false
    return
  }
  previewLoading.value = true
  if (immediate) {
    void runPreview(seq)
  } else {
    previewTimer = window.setTimeout(() => void runPreview(seq), 300)
  }
}

function retryPreview() {
  schedulePreview(true)
}

watch([() => filledIds.value.join(','), teaCents], () => schedulePreview())

function close() {
  resetPreviewState()
  emit('update:modelValue', false)
}

async function submit() {
  if (!filledCount.value) {
    ElMessage.warning('请至少选择 1 个玩家')
    return
  }
  if (!previewReady.value) {
    ElMessage.warning(
      previewState.value === 'loading' ? '正在校验押金，请稍候' : '押金校验失败，请先重试',
    )
    return
  }
  if (preview.value && preview.value.negative_count > 0) {
    try {
      await ElMessageBox.confirm(
        `有 ${preview.value.negative_count} 人会扣成负数：${preview.value.negative_players.join('、')}。仍要创建吗？`,
        '押金会变成负数',
        { confirmButtonText: '仍然创建', cancelButtonText: '再想想', type: 'warning' },
      )
    } catch {
      return
    }
  }

  saving.value = true
  try {
    const created = await sessionApi.create({
      tea_fee_cents: teaCents.value,
      player_ids: filledIds.value,
    })
    if (created.tea_free_removed?.length) {
      ElMessage.info(`已自动去掉免茶水玩家：${created.tea_free_removed.join('、')}`)
    }
    ElMessage.success('场次已创建')
    emit('created', {})
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.players-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.players-head .section-title {
  margin: 0;
}

.count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.count.full {
  color: var(--el-color-warning);
}

.slots {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 14px;
  margin-bottom: 10px;
}

.slot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 4px;
  border-radius: 8px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
}

.slot.empty {
  border-style: dashed;
}

.idx {
  width: 30px;
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.clear {
  font-size: 12px;
}

.add-row {
  margin-bottom: 12px;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  padding: 10px 12px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}

.summary b {
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.danger {
  color: var(--el-color-danger);
}

.warn {
  color: var(--el-color-warning);
}

.small {
  font-size: 11.5px;
}
</style>
