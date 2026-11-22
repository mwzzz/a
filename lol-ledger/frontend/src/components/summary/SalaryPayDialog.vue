<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { playerApi, salaryApi } from '@/api'
import type { PlayerOption, SalaryPreviewItem } from '@/api/types'
import { formatCents } from '@/utils/money'

interface Row extends SalaryPreviewItem {
  checked: boolean
}

const props = defineProps<{ modelValue: boolean; dateFrom: string; dateTo: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; paid: [] }>()

const loading = ref(false)
const submitting = ref(false)
const rows = ref<Row[]>([])
const wageDate = ref('')
const lastBatchId = ref<string | null>(null)

const pickerVisible = ref(false)
const pickingRow = ref<Row | null>(null)
const pickerKeyword = ref('')
const pickerOptions = ref<PlayerOption[]>([])
const pickerLoading = ref(false)

function errDetail(e: unknown, fallback: string): string {
  const resp = (e as { response?: { data?: { detail?: string } } })?.response
  return resp?.data?.detail || fallback
}

async function load() {
  loading.value = true
  try {
    const data = await salaryApi.preview(props.dateFrom, props.dateTo)
    wageDate.value = data.wage_date
    rows.value = data.items.map((item) => ({ ...item, checked: !item.paid }))
    lastBatchId.value = data.items.find((item) => item.paid_batch_id)?.paid_batch_id ?? null
  } catch {
    ElMessage.error('发工资预览加载失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      lastBatchId.value = null
      void load()
    }
  },
)

const unpaid = computed(() => rows.value.filter((row) => !row.paid))
const selected = computed(() => unpaid.value.filter((row) => row.checked))
const selectedUnbound = computed(() => selected.value.filter((row) => !row.salary_player_id))
const selectedTotal = computed(() =>
  selected.value.reduce((sum, row) => sum + row.amount_cents, 0),
)

async function openPicker(row: Row) {
  pickingRow.value = row
  pickerKeyword.value = ''
  pickerVisible.value = true
  await searchPlayers()
}

async function searchPlayers() {
  pickerLoading.value = true
  try {
    pickerOptions.value = await playerApi.options({ keyword: pickerKeyword.value, limit: 20 })
  } catch {
    pickerOptions.value = []
  } finally {
    pickerLoading.value = false
  }
}

async function choosePlayer(player: PlayerOption) {
  const row = pickingRow.value
  if (!row) return
  try {
    await salaryApi.bind(row.user_id, player.id)
    row.salary_player_id = player.id
    row.salary_player_game_id = player.game_id
    pickerVisible.value = false
    ElMessage.success(`已把「${row.display_name}」的工资账户设为 ${player.game_id}`)
  } catch (e) {
    ElMessage.error(errDetail(e, '绑定失败'))
  }
}

async function confirmPay() {
  if (!selected.value.length) {
    ElMessage.warning('没有勾选要发放的人')
    return
  }
  if (selectedUnbound.value.length) {
    ElMessage.warning(
      `还有 ${selectedUnbound.value.length} 人未绑定工资账户：${selectedUnbound.value
        .map((row) => row.display_name)
        .join('、')}`,
    )
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认给 ${selected.value.length} 人发工资，共 ¥${formatCents(selectedTotal.value)}？` +
        '将加押金到各自绑定的工资账户。',
      '确认发工资',
      { type: 'warning', confirmButtonText: '确认发放', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    const res = await salaryApi.pay({
      date_from: props.dateFrom,
      date_to: props.dateTo,
      user_ids: selected.value.map((row) => row.user_id),
    })
    lastBatchId.value = res.batch_id
    ElMessage.success(`已发放 ${res.lines.length} 人，共 ¥${formatCents(res.total_cents)}`)
    emit('paid')
    await load()
  } catch (e) {
    ElMessage.error(errDetail(e, '发放失败'))
  } finally {
    submitting.value = false
  }
}

async function voidLast() {
  if (!lastBatchId.value) return
  try {
    await ElMessageBox.confirm(
      '撤销会把这批工资从各账户退回（若已被消费会失败）。确认撤销这批？',
      '撤销这批工资',
      { type: 'warning', confirmButtonText: '确认撤销', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    const res = await salaryApi.void(lastBatchId.value)
    ElMessage.success(`已撤销，退回 ¥${formatCents(res.total_cents)}`)
    lastBatchId.value = null
    emit('paid')
    await load()
  } catch (e) {
    ElMessage.error(errDetail(e, '撤销失败'))
  } finally {
    submitting.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="发工资" width="720px" @update:model-value="close">
    <div class="tip">
      工资额 = 该区间本人分红（与「生成工资汇总」一致），加押金到绑定的工资账户，不触发充值活动。
      <template v-if="wageDate"> 工资日：{{ wageDate }}。</template>
    </div>

    <el-table v-loading="loading" :data="rows" size="small" max-height="360">
      <el-table-column label="发放" width="60">
        <template #default="{ row }">
          <el-checkbox v-model="row.checked" :disabled="row.paid" />
        </template>
      </el-table-column>
      <el-table-column label="店员" prop="display_name" min-width="90" />
      <el-table-column label="工资" width="90" align="right">
        <template #default="{ row }">¥{{ formatCents(row.amount_cents) }}</template>
      </el-table-column>
      <el-table-column label="到账账户" min-width="180">
        <template #default="{ row }">
          <template v-if="row.salary_player_game_id">
            <span>{{ row.salary_player_game_id }}</span>
            <el-button link type="primary" size="small" @click="openPicker(row)">修改</el-button>
          </template>
          <el-button v-else link type="primary" size="small" @click="openPicker(row)">
            选择账户
          </el-button>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-tag v-if="row.paid" type="success" size="small">
            已发 ¥{{ formatCents(row.paid_amount_cents) }}
          </el-tag>
          <span v-else class="muted">待发</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      :model-value="pickerVisible"
      title="选择工资账户"
      width="420px"
      append-to-body
      @update:model-value="pickerVisible = false"
    >
      <el-input v-model="pickerKeyword" placeholder="搜索游戏名" clearable @input="searchPlayers" />
      <div v-loading="pickerLoading" class="picker-list">
        <div v-for="p in pickerOptions" :key="p.id" class="picker-item" @click="choosePlayer(p)">
          <span>{{ p.game_id }}</span>
          <span class="muted small">余额 ¥{{ formatCents(p.balance_cents) }}</span>
        </div>
        <div v-if="!pickerLoading && !pickerOptions.length" class="muted small">没有匹配玩家</div>
      </div>
    </el-dialog>

    <template #footer>
      <div class="foot">
        <span>合计 <b>¥{{ formatCents(selectedTotal) }}</b> · 已选 {{ selected.length }} 人</span>
        <div class="foot-actions">
          <el-button v-if="lastBatchId" :loading="submitting" @click="voidLast">撤销这批</el-button>
          <el-button @click="close">关闭</el-button>
          <el-button type="primary" :loading="submitting" @click="confirmPay">确认发放</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.tip {
  font-size: 12px;
  color: var(--app-text-muted);
  margin-bottom: 10px;
  line-height: 1.6;
}

.picker-list {
  margin-top: 10px;
  max-height: 260px;
  overflow: auto;
}

.picker-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
}

.picker-item:hover {
  background: var(--app-bg-panel);
}

.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.foot-actions {
  display: flex;
  gap: 8px;
}
</style>
