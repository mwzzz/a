<template>
  <div class="dividend-view">
    <div class="toolbar">
      <el-date-picker
        v-model="dateRange"
        type="datetimerange"
        value-format="YYYY-MM-DDTHH:mm:ss"
        format="MM-DD HH:mm:ss"
        range-separator="至"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        :shortcuts="shortcuts"
        unlink-panels
        style="width: 330px"
        @change="reload"
      />
      <el-button :icon="Refresh" @click="reload">刷新</el-button>
      <div class="spacer"></div>
      <el-button
        type="primary"
        :disabled="!selected.length"
        @click="openSettle"
      >
        结算选中（{{ selected.length }} 人）
      </el-button>
    </div>

    <div v-if="preview?.warnings.length" class="warn">
      {{ preview.warnings.join('；') }}
    </div>

    <div class="summary-grid">
      <div class="summary">
        <span>待结算分红</span>
        <b>¥{{ formatCents(preview?.totals.pending_dividend_cents || 0) }}</b>
      </div>
      <div class="summary">
        <span>待结算茶水</span>
        <b>¥{{ formatCents(preview?.totals.pending_tea_cents || 0) }}</b>
      </div>
      <div class="summary">
        <span>涉及操作人</span>
        <b>{{ preview?.totals.operator_count || 0 }}</b>
      </div>
      <div class="summary">
        <span>本区间场次</span>
        <b>{{ preview?.totals.session_count || 0 }}</b>
      </div>
    </div>

    <div class="panel block">
      <div class="section-head">
        <div class="section-title">按操作人汇总</div>
        <span class="muted small">
          {{ formatMoment(preview?.period.start) }} 至
          {{ formatMoment(preview?.period.end) }}，只算还没结算过的场次
          <template v-if="preview?.totals.claimed_session_count">
            （本区间已有 {{ preview.totals.claimed_session_count }} 场结算过）
          </template>
        </span>
      </div>
      <el-table
        v-loading="loading"
        class="desktop-only"
        :data="preview?.items || []"
        :row-key="(row: DividendPreviewItem) => row.user?.id || 0"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="44" :selectable="isSelectable" />
        <el-table-column label="操作人" min-width="160">
          <template #default="{ row }">
            <div class="cell-main">
              {{ row.user?.display_name || '未知' }}
              <el-tag v-if="!row.is_active" type="info" size="small" effect="plain">已停用</el-tag>
            </div>
            <div class="cell-sub">
              {{ row.user?.username || '-' }}
              <span v-if="row.pending.dividend_cents > 0"> · {{ modeLabel(row.dividend_mode) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="场次" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.pending.session_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="局数" width="80" align="right">
          <template #default="{ row }"><span class="mono">{{ row.pending.session_count }}</span></template>
        </el-table-column>
        <el-table-column label="人次" width="80" align="right">
          <template #default="{ row }"><span class="mono">{{ row.pending.player_times }}</span></template>
        </el-table-column>
        <el-table-column label="茶水" width="110" align="right">
          <template #default="{ row }"><span class="mono">¥{{ formatCents(row.pending.tea_cents) }}</span></template>
        </el-table-column>
        <el-table-column label="待结分红" width="110" align="right">
          <template #default="{ row }">
            <b class="money-cell">¥{{ formatCents(row.pending.dividend_cents) }}</b>
          </template>
        </el-table-column>
        <el-table-column label="已结分红" width="110" align="right">
          <template #default="{ row }">
            <span class="mono muted">¥{{ formatCents(row.settled.dividend_cents) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusTag
              :type="row.status === 'pending' ? 'warning' : row.status === 'settled' ? 'success' : 'info'"
              :label="row.status === 'pending' ? '待结算' : row.status === 'settled' ? '已结清' : '无分红'"
            />
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!loading && !preview?.items.length" class="empty-hint desktop-only">
        这个区间没有可结算的分红
      </div>

      <div v-loading="loading" class="preview-cards mobile-only">
        <div
          v-for="row in preview?.items || []"
          :key="row.user?.id || 0"
          class="preview-card"
          :class="{ selected: isSelected(row) }"
        >
          <div class="preview-card-head">
            <el-checkbox
              :model-value="isSelected(row)"
              :disabled="!isSelectable(row)"
              @change="toggleSelect(row)"
            />
            <div class="preview-name">
              <div class="cell-main">
              {{ row.user?.display_name || '未知' }}
              <el-tag v-if="!row.is_active" type="info" size="small" effect="plain">已停用</el-tag>
            </div>
              <div class="cell-sub">
                {{ row.user?.username || '-' }}
                <span v-if="row.pending.dividend_cents > 0"> · {{ modeLabel(row.dividend_mode) }}</span>
              </div>
            </div>
            <StatusTag
              :type="row.status === 'pending' ? 'warning' : row.status === 'settled' ? 'success' : 'info'"
              :label="row.status === 'pending' ? '待结算' : row.status === 'settled' ? '已结清' : '无分红'"
            />
          </div>
          <div class="preview-card-grid">
            <div><span>场次</span><b>{{ row.pending.session_count }}</b></div>
            <div><span>局数/人次</span><b>{{ row.pending.session_count }}/{{ row.pending.player_times }}</b></div>
            <div><span>茶水</span><b>¥{{ formatCents(row.pending.tea_cents) }}</b></div>
            <div><span>待结分红</span><b class="good">¥{{ formatCents(row.pending.dividend_cents) }}</b></div>
            <div><span>已结分红</span><b class="muted">¥{{ formatCents(row.settled.dividend_cents) }}</b></div>
          </div>
        </div>
        <div v-if="!loading && !preview?.items.length" class="empty-hint">
          这个区间没有可结算的分红
        </div>
      </div>
    </div>

    <div class="panel block history">
      <div class="section-head">
        <div class="section-title">结算记录</div>
        <div class="spacer"></div>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="historyTotal"
          layout="prev, pager, next"
          small
          @current-change="loadHistory"
        />
      </div>
      <el-table class="desktop-only" :data="history" empty-text="还没有结算记录">
        <el-table-column label="结算时间" width="150">
          <template #default="{ row }">
            <span class="muted">{{ formatShort(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作人" min-width="140">
          <template #default="{ row }">{{ row.user.display_name || row.user.username }}</template>
        </el-table-column>
        <el-table-column label="区间" width="190">
          <template #default="{ row }">
          {{ formatMoment(row.period.start) }} 至 {{ formatMoment(row.period.end) }}
        </template>
        </el-table-column>
        <el-table-column label="局数" width="70" align="right">
          <template #default="{ row }"><span class="mono">{{ row.session_count }}</span></template>
        </el-table-column>
        <el-table-column label="茶水" width="100" align="right">
          <template #default="{ row }"><span class="mono">¥{{ formatCents(row.tea_cents) }}</span></template>
        </el-table-column>
        <el-table-column label="分红" width="100" align="right">
          <template #default="{ row }">
            <b class="money-cell">¥{{ formatCents(row.dividend_cents) }}</b>
          </template>
        </el-table-column>
        <el-table-column label="经办" width="110">
          <template #default="{ row }">{{ row.settled_by?.display_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="140">
          <template #default="{ row }"><span class="muted">{{ row.note || '-' }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'voided'" type="info" size="small" effect="plain">已冲销</el-tag>
            <el-tag v-else type="success" size="small" effect="plain">已生效</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'live'"
              link
              type="danger"
              :loading="voiding"
              @click="voidOne(row)"
            >
              撤销结算
            </el-button>
            <span v-else class="muted">{{ row.void_note || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="history-cards mobile-only">
        <div v-for="row in history" :key="row.id" class="history-card">
          <div class="history-card-head">
            <span class="cell-main">
              {{ row.user.display_name || row.user.username }}
              <el-tag v-if="row.status === 'voided'" type="info" size="small" effect="plain">已冲销</el-tag>
            </span>
            <b :class="row.status === 'voided' ? 'muted' : 'good'">
              ¥{{ formatCents(row.dividend_cents) }}
            </b>
          </div>
          <div class="history-card-meta">
            <span>{{ formatShort(row.created_at) }}</span>
            <span>{{ formatMoment(row.period.start) }} 至 {{ formatMoment(row.period.end) }}</span>
            <span>茶水 ¥{{ formatCents(row.tea_cents) }} · {{ row.session_count }} 局</span>
            <span>经办 {{ row.settled_by?.display_name || '-' }}</span>
          </div>
          <div v-if="row.note" class="cell-sub">{{ row.note }}</div>
          <div v-if="row.status === 'live'" class="cell-sub">
            <el-button link type="danger" :loading="voiding" @click="voidOne(row)">
              撤销结算
            </el-button>
          </div>
        </div>
        <div v-if="!history.length" class="empty-hint">还没有结算记录</div>
      </div>
    </div>

    <el-dialog v-model="settleVisible" title="确认分红结算" width="480px" :close-on-click-modal="false">
      <div class="settle-summary">
        <div><span>操作人</span><b>{{ selected.length }} 人</b></div>
        <div><span>待结茶水</span><b>¥{{ formatCents(selectedTea) }}</b></div>
        <div><span>待结分红</span><b class="good">¥{{ formatCents(selectedDividend) }}</b></div>
        <div>
          <span>结算区间</span>
          <b>{{ formatMoment(preview?.period.start) }} 至 {{ formatMoment(preview?.period.end) }}</b>
        </div>
      </div>
      <el-input
        v-model="note"
        type="textarea"
        :rows="3"
        maxlength="200"
        placeholder="备注，比如「微信已转」"
      />
      <div class="settle-tip">
        结算会把区间内这些场次逐局登记为已结算，之后任何区间都不会再重复发钱；
        万一算错，可以在下面的结算记录里点「撤销结算」冲销重来。
      </div>
      <template #footer>
        <el-button @click="settleVisible = false">取消</el-button>
        <el-button type="primary" :loading="settling" @click="submitSettle">确认结算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { dividendApi } from '@/api'
import type {
  DividendPreview,
  DividendPreviewItem,
  DividendSettlementRow,
} from '@/api/types'
import StatusTag from '@/components/common/StatusTag.vue'
import { formatMoment, formatShort } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

function dayText(value: Date): string {
  const y = value.getFullYear()
  const m = String(value.getMonth() + 1).padStart(2, '0')
  const d = String(value.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function startOfDay(offset = 0): Date {
  const date = new Date()
  date.setDate(date.getDate() - offset)
  date.setHours(0, 0, 0, 0)
  return date
}

function endOfDay(offset = 0): Date {
  const date = new Date()
  date.setDate(date.getDate() - offset)
  date.setHours(23, 59, 59, 0)
  return date
}

function startOfMonth(offset = 0): Date {
  const today = new Date()
  return new Date(today.getFullYear(), today.getMonth() + offset, 1, 0, 0, 0, 0)
}

function endOfMonth(offset = 0): Date {
  const today = new Date()
  return new Date(today.getFullYear(), today.getMonth() + offset + 1, 0, 23, 59, 59, 0)
}

function momentText(value: Date): string {
  const hh = String(value.getHours()).padStart(2, '0')
  const mm = String(value.getMinutes()).padStart(2, '0')
  const ss = String(value.getSeconds()).padStart(2, '0')
  return `${dayText(value)}T${hh}:${mm}:${ss}`
}

const shortcuts = [
  { text: '今天', value: () => [startOfDay(0), endOfDay(0)] },
  { text: '昨天', value: () => [startOfDay(1), endOfDay(1)] },
  { text: '本月', value: () => [startOfMonth(0), endOfDay(0)] },
  { text: '上月', value: () => [startOfMonth(-1), endOfMonth(-1)] },
  { text: '近 30 天', value: () => [startOfDay(29), endOfDay(0)] },
]

const dateRange = ref<[string, string]>([momentText(startOfMonth(0)), momentText(endOfDay(0))])
const preview = ref<DividendPreview | null>(null)
const loading = ref(false)
const selected = ref<DividendPreviewItem[]>([])
const settleVisible = ref(false)
const settling = ref(false)
const voiding = ref(false)
const note = ref('')
const history = ref<DividendSettlementRow[]>([])
const historyTotal = ref(0)
const page = ref(1)
const pageSize = 10

const selectedTea = computed(() =>
  selected.value.reduce((sum, item) => sum + item.pending.tea_cents, 0),
)
const selectedDividend = computed(() =>
  selected.value.reduce((sum, item) => sum + item.pending.dividend_cents, 0),
)

function isSelectable(row: DividendPreviewItem): boolean {
  return row.pending.dividend_cents > 0
}

/** 分红口径提示：同一个区间可能既有按茶水比例的场次，也有按局固定的场次 */
function modeLabel(mode: DividendPreviewItem['dividend_mode']): string {
  if (mode === 'fixed') return '按每局固定'
  if (mode === 'percent') return '按茶水比例'
  if (mode === 'mixed') return '两种口径混合'
  return ''
}

function onSelectionChange(rows: DividendPreviewItem[]) {
  selected.value = rows
}

function isSelected(row: DividendPreviewItem): boolean {
  const id = row.user?.id
  return !!id && selected.value.some((item) => item.user?.id === id)
}

/** 手机端用卡片上的复选框选择操作人 */
function toggleSelect(row: DividendPreviewItem) {
  const id = row.user?.id
  if (!id || !isSelectable(row)) return
  selected.value = isSelected(row)
    ? selected.value.filter((item) => item.user?.id !== id)
    : [...selected.value, row]
}

async function loadPreview() {
  loading.value = true
  try {
    preview.value = await dividendApi.preview(dateRange.value?.[0], dateRange.value?.[1])
    selected.value = []
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  const payload = await dividendApi.settlements(page.value, pageSize)
  history.value = payload.items
  historyTotal.value = payload.total
}

async function reload() {
  page.value = 1
  await Promise.all([loadPreview(), loadHistory()])
}

function openSettle() {
  if (!selected.value.length) {
    ElMessage.warning('请先勾选要结算的操作人')
    return
  }
  note.value = ''
  settleVisible.value = true
}

async function submitSettle() {  settling.value = true
  try {
    await dividendApi.settle({
      user_ids: selected.value.map((item) => item.user?.id as number),
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      note: note.value.trim(),
    })
    ElMessage.success(`已结算 ${selected.value.length} 人`)
    settleVisible.value = false
    await reload()
  } finally {
    settling.value = false
  }
}

/** 冲销一笔结算：场次重新变为待结算，已发出去的钱要线下追回 */
async function voidOne(row: DividendSettlementRow) {
  const who = row.user.display_name || row.user.username
  let reason = ''
  try {
    const answer = await ElMessageBox.prompt(
      `冲销 ${who} 的 ¥${formatCents(row.dividend_cents)}？` +
        `${row.claimed_session_count} 场会重新变成待结算。` +
        '已发出去的钱不会自动扣回，需要线下追回。',
      '撤销结算',
      {
        confirmButtonText: '确认冲销',
        cancelButtonText: '取消',
        type: 'warning',
        inputPlaceholder: '备注：为什么要冲销',
        inputValidator: (text: string) =>
          (text || '').trim().length >= 2 || '请写清冲销原因',
      },
    )
    reason = String(answer.value || '').trim()
  } catch {
    return
  }
  voiding.value = true
  try {
    await dividendApi.voidSettlement(row.id, reason)
    ElMessage.success('已冲销，这些场次重新变为待结算')
    await reload()
  } finally {
    voiding.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.dividend-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.warn {
  padding: 8px 12px;
  border-radius: var(--app-radius-sm);
  background: var(--app-warning-soft);
  color: var(--el-color-warning);
  font-size: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  background: var(--app-bg-panel);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  font-size: 12px;
  color: var(--app-text-muted);
}

.summary b {
  font-size: 20px;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.block {
  padding: 14px 16px;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.section-head .section-title {
  margin: 0;
}

.small {
  font-size: 12px;
}

.history {
  margin-bottom: 8px;
}

.settle-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: var(--app-radius-sm);
  background: var(--app-bg-subtle);
  font-size: 12.5px;
}

.settle-summary > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.settle-summary span {
  color: var(--app-text-muted);
}

.settle-summary .good {
  color: var(--el-color-success);
}

.settle-tip {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.preview-card,
.history-card {
  padding: 10px 12px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.preview-card + .preview-card,
.history-card + .history-card {
  margin-top: 8px;
}

.preview-card.selected {
  border-color: var(--el-color-primary);
  background: var(--app-bg-elevated);
}

.preview-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-name {
  flex: 1;
  min-width: 0;
}

.preview-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px 10px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--app-border);
}

.preview-card-grid > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.preview-card-grid b {
  font-size: 13px;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.preview-card-grid b.good,
.history-card-head b {
  color: var(--el-color-success);
}

.history-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.history-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .section-head {
    flex-wrap: wrap;
    row-gap: 2px;
  }

  .section-head .small {
    flex: 1 1 100%;
    line-height: 1.5;
  }

  .dividend-view :deep(.el-table) {
    font-size: 12px;
  }
}
</style>
