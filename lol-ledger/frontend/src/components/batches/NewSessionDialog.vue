<template>
  <el-dialog
    :model-value="modelValue"
    title="新增场次"
    width="720px"
    top="6vh"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div class="grid">
      <div class="field">
        <label>场次名称</label>
        <el-input v-model="name" placeholder="留空自动生成，如 10月31日 第1局" maxlength="64" />
      </div>
      <div class="field">
        <label>场次时间</label>
        <el-date-picker
          v-model="playedAt"
          type="datetime"
          placeholder="默认现在"
          style="width: 100%"
        />
      </div>
      <div class="field">
        <label>备注</label>
        <el-input v-model="note" placeholder="可选" maxlength="200" />
      </div>
      <div class="field">
        <label>每人茶水（元）</label>
        <el-input v-model="teaYuan" placeholder="2.00" autocomplete="off">
          <template #prefix>¥</template>
        </el-input>
      </div>
    </div>

    <div class="ai-box" @click="notReady" @paste.prevent="notReady" @dragover.prevent @drop.prevent="notReady">
      <div class="ai-head">
        <span class="ai-title">AI 识别玩家</span>
        <span class="dim-tag">即将上线</span>
      </div>
      <div class="ai-body">
        <el-icon class="ai-icon"><Picture /></el-icon>
        <div>点击此处，然后 Ctrl+V 粘贴截图</div>
        <div class="ai-sub">或把截图拖到这里，自动识别并填入玩家（下一期上线）</div>
      </div>
    </div>

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
          :placeholder="slot ? '已选择' : '+ 添加'"
        />
        <el-button v-if="slot" link type="info" class="clear" @click="slots[index] = null">
          清空
        </el-button>
      </div>
    </div>

    <div class="add-row">
      <PlayerSelect v-model="adding" :exclude-ids="selectedIds" placeholder="搜索并添加玩家" />
    </div>

    <div class="summary">
      <span>已选 <b>{{ filledCount }}</b> 人</span>
      <span>茶水合计 <b>¥{{ formatCents(teaTotalCents) }}</b></span>
      <span v-if="preview && preview.negative_count" class="danger">
        有 {{ preview.negative_count }} 人会扣成负数：{{ preview.negative_players.join('、') }}
      </span>
      <span v-else-if="filledCount" class="muted">没有人的押金会被扣成负数</span>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { Picture } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { sessionApi } from '@/api'
import type { PreviewPayload } from '@/api/types'
import PlayerSelect from '@/components/common/PlayerSelect.vue'
import { toIso } from '@/utils/datetime'
import { formatCents, parseYuan } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
  batchId: number | null
  defaultTeaCents: number
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created', value: { batchId: number }): void
}>()

const name = ref('')
const note = ref('')
const playedAt = ref<Date | null>(new Date())
const teaYuan = ref('2.00')
const slots = ref<(number | null)[]>(Array(10).fill(null))
const adding = ref<number | null>(null)
const saving = ref(false)
const preview = ref<PreviewPayload | null>(null)

const filledIds = computed(() => slots.value.filter((item): item is number => Boolean(item)))
const filledCount = computed(() => filledIds.value.length)
const selectedIds = computed(() => filledIds.value)

const teaCents = computed(() => parseYuan(teaYuan.value))

const teaTotalCents = computed(() =>
  teaCents.value === null ? 0 : teaCents.value * filledCount.value,
)

function otherSelected(index: number): number[] {
  return slots.value.filter((item, position) => Boolean(item) && position !== index) as number[]
}

function notReady() {
  ElMessage.info('AI 识别玩家即将上线，这一期先手动选人')
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    name.value = ''
    note.value = ''
    playedAt.value = new Date()
    teaYuan.value = formatCents(props.defaultTeaCents || 200)
    slots.value = Array(10).fill(null)
    adding.value = null
    preview.value = null
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

function schedulePreview() {
  window.clearTimeout(previewTimer)
  if (!filledCount.value || teaCents.value === null) {
    preview.value = null
    return
  }
  previewTimer = window.setTimeout(async () => {
    try {
      preview.value = await sessionApi.preview(filledIds.value, teaCents.value as number)
    } catch {
      preview.value = null
    }
  }, 300)
}

watch([() => filledIds.value.join(','), teaCents], schedulePreview)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  if (!props.batchId) {
    ElMessage.warning('当前没有进行中的批次，请先开班')
    return
  }
  if (!filledCount.value) {
    ElMessage.warning('请至少选择 1 个玩家')
    return
  }
  if (teaCents.value === null) {
    ElMessage.warning('茶水金额格式不正确')
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
    await sessionApi.create({
      batch_id: props.batchId,
      name: name.value.trim(),
      played_at: toIso(playedAt.value) || null,
      note: note.value.trim(),
      tea_fee_cents: teaCents.value,
      player_ids: filledIds.value,
    })
    ElMessage.success('场次已创建')
    emit('created', { batchId: props.batchId })
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 12px 16px;
  margin-bottom: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}

.ai-box {
  border: 1px dashed #303745;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 16px;
  cursor: pointer;
  background: #101319;
  transition: border-color 0.15s ease;
}

.ai-box:hover {
  border-color: var(--el-color-primary);
}

.ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ai-title {
  font-size: 13px;
  font-weight: 600;
}

.ai-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 0 10px;
  color: var(--el-text-color-secondary);
  font-size: 12.5px;
}

.ai-icon {
  font-size: 26px;
  color: #3c4353;
}

.ai-sub {
  font-size: 11.5px;
  color: #5d6575;
}

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
  background: #101319;
  border: 1px solid #1e222b;
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
  background: #101319;
  border: 1px solid #1e222b;
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

.small {
  font-size: 11.5px;
}
</style>
