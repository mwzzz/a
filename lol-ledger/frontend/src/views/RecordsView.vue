<template>
  <div class="page" :class="{ embedded }">
    <div v-if="!embedded" class="page-head">
      <span class="page-title">记录管理</span>
      <span class="page-sub">押金变动与场次流水，最新在前</span>
    </div>

    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索玩家名或场次名"
        clearable
        style="width: 260px"
        @keyup.enter="reload"
        @clear="reload"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-date-picker
        v-model="dateRange"
        type="datetimerange"
        value-format="YYYY-MM-DDTHH:mm:ss"
        format="MM-DD HH:mm:ss"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        :shortcuts="shortcuts"
        style="width: 320px"
        @change="reload"
      />

      <el-select v-if="tab === 'deposits'" v-model="reason" placeholder="全部原因" style="width: 150px" @change="reload">
        <el-option label="全部原因" value="" />
        <el-option label="正常扣押" value="normal_deduct" />
        <el-option label="加押金" value="add_deposit" />
        <el-option label="加赠金" value="add_bonus" />
        <el-option label="退押金" value="refund" />
        <el-option label="划押转出" value="transfer_out" />
        <el-option label="划押转入" value="transfer_in" />
      </el-select>

      <el-select
        v-model="operatorId"
        placeholder="全部操作人"
        clearable
        style="width: 160px"
        @change="reload"
      >
        <el-option v-for="op in operators" :key="op.id" :label="op.display_name" :value="op.id">
          {{ op.display_name }}
          <span class="muted small">
            {{ op.username }}{{ op.is_active ? '' : '（已停用）' }}
          </span>
        </el-option>
      </el-select>

      <el-button :icon="Refresh" @click="reload">刷新</el-button>
      <div class="spacer"></div>
      <span class="muted small">共 {{ total }} 条</span>
    </div>

    <div v-if="tab === 'deposits' && operatorId && cashSummary" class="cash-summary">
      <span>操作人：<b>{{ cashSummary.operator?.display_name || '-' }}</b></span>
      <span>收押金 <b>¥{{ formatCents(cashSummary.add_deposit_cents) }}</b></span>
      <span>退押金 <b>¥{{ formatCents(cashSummary.refund_cents) }}</b></span>
      <span :class="cashSummary.cash_diff_cents < 0 ? 'diff-out' : 'diff-in'">
        差额 <b>¥{{ formatCents(cashSummary.cash_diff_cents) }}</b>
      </span>
      <span class="muted small">
        {{ cashSummary.cash_diff_cents < 0 ? '店长应补' : '店员应交' }}，按当前时间范围统计
      </span>
    </div>

    <el-tabs v-model="tab" @tab-change="onTabChange">
      <el-tab-pane label="押金记录" name="deposits">
        <div class="panel desktop-only">
          <el-table v-loading="loading" :data="entries">
            <el-table-column label="时间" width="168">
              <template #default="{ row }">
                <span class="muted nowrap">{{ formatFull(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="玩家" min-width="150">
              <template #default="{ row }">
                <span class="cell-main">{{ row.player.game_id }}</span>
              </template>
            </el-table-column>
            <el-table-column label="变动金额" width="120" align="right">
              <template #default="{ row }">
                <MoneyText :cents="row.signed_amount_cents" change />
              </template>
            </el-table-column>
            <el-table-column label="变动后余额" width="140" align="right">
              <template #default="{ row }">
                <span class="mono muted">¥{{ formatCents(row.balance_after_cents) }}</span>
                <div v-if="row.bonus_after_cents > 0" class="cell-sub">
                  赠金 ¥{{ formatCents(row.bonus_after_cents) }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作人" width="96">
              <template #default="{ row }">
                <span class="muted">{{ row.operator?.display_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="原因" min-width="200">
              <template #default="{ row }">
                <div class="cell-main">{{ row.reason_label }}</div>
                <div v-if="row.note" class="cell-sub">{{ row.note }}</div>
                <div v-if="row.bonus_amount_cents > 0" class="cell-sub">
                  其中赠金抵扣 ¥{{ formatCents(row.bonus_amount_cents) }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="场次" min-width="150">
              <template #default="{ row }">
                <span class="muted">{{ row.session?.name || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!loading && !entries.length" class="empty-hint">没有记录</div>
        </div>

        <div class="mobile-only">
          <div v-loading="loading" class="record-cards">
            <div v-for="row in entries" :key="row.id" class="record-card">
              <div class="record-card-head">
                <span class="cell-main">{{ row.player.game_id }}</span>
                <MoneyText :cents="row.signed_amount_cents" change />
              </div>
              <div class="cell-sub">
                {{ row.reason_label }}
                <template v-if="row.note"> · {{ row.note }}</template>
                <template v-if="row.bonus_amount_cents > 0">
                  · 赠金抵扣 ¥{{ formatCents(row.bonus_amount_cents) }}
                </template>
              </div>
              <div class="record-card-meta">
                <span>{{ formatFull(row.created_at) }}</span>
                <span class="mono">余额 ¥{{ formatCents(row.balance_after_cents) }}</span>
                <span v-if="row.bonus_after_cents > 0">
                  赠金 ¥{{ formatCents(row.bonus_after_cents) }}
                </span>
                <span>{{ row.operator?.display_name || '-' }}</span>
                <span v-if="row.session">{{ row.session.name }}</span>
              </div>
            </div>
            <div v-if="!loading && !entries.length" class="empty-hint">没有记录</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="场次记录" name="sessions">
        <div class="panel desktop-only">
          <el-table v-loading="loading" :data="sessions">
            <el-table-column label="时间" width="140">
              <template #default="{ row }">
                <span class="muted nowrap">{{ formatShort(row.played_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="场次名" min-width="200">
              <template #default="{ row }">
                <span class="cell-main">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="人数" width="80" align="right">
              <template #default="{ row }">
                <span class="mono">{{ row.player_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="茶水/人" width="110" align="right">
              <template #default="{ row }">
                <span class="mono">¥{{ formatCents(row.tea_fee_cents) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="茶水合计" width="120" align="right">
              <template #default="{ row }">
                <span class="mono">¥{{ formatCents(row.tea_total_cents) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作人" width="100">
              <template #default="{ row }">
                <span class="muted">{{ row.operator?.display_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="玩家" min-width="260">
              <template #default="{ row }">
                <span class="muted players">{{ row.players.map((p: any) => p.game_id).join('、') }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.voidable"
                  link
                  type="warning"
                  @click="voidSession(row)"
                >
                  撤回
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!loading && !sessions.length" class="empty-hint">没有记录</div>
        </div>

        <div class="mobile-only">
          <div v-loading="loading" class="record-cards">
            <div v-for="row in sessions" :key="row.id" class="record-card">
              <div class="record-card-head">
                <span class="cell-main">{{ row.name }}</span>
                <span class="mono">{{ row.player_count }} 人</span>
              </div>
              <div class="cell-sub">
                茶水 ¥{{ formatCents(row.tea_fee_cents) }}/人 · 合计 ¥{{ formatCents(row.tea_total_cents) }}
              </div>
              <div class="record-card-meta">
                <span>{{ formatShort(row.played_at) }}</span>
                <span>操作人 {{ row.operator?.display_name || '-' }}</span>
              </div>
              <div class="record-card-players">{{ row.players.map((p) => p.game_id).join('、') }}</div>
              <div v-if="row.voidable" class="record-card-actions">
                <el-button link type="warning" @click="voidSession(row)">撤回这一局</el-button>
              </div>
            </div>
            <div v-if="!loading && !sessions.length" class="empty-hint">没有记录</div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="reload"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { recordApi, sessionApi } from '@/api'
import type { LedgerEntryRow, OperatorCashSummary, OperatorOption, SessionRow } from '@/api/types'
import MoneyText from '@/components/common/MoneyText.vue'
import { useAppStore } from '@/stores/app'
import { formatFull, formatShort, momentShortcuts } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const route = useRoute()
const app = useAppStore()

withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })

const shortcuts = momentShortcuts()
const tab = ref<'deposits' | 'sessions'>('deposits')
const keyword = ref('')
const dateRange = ref<[string, string] | null>(null)
const reason = ref('')
const operatorId = ref<number | ''>('')
const operators = ref<OperatorOption[]>([])
const cashSummary = ref<OperatorCashSummary | null>(null)
const entries = ref<LedgerEntryRow[]>([])
const sessions = ref<SessionRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function loadOperators() {
  try {
    operators.value = await recordApi.operators()
  } catch {
    operators.value = []
  }
}

async function loadCashSummary() {
  if (!operatorId.value) {
    cashSummary.value = null
    return
  }
  try {
    cashSummary.value = await recordApi.operatorSummary({
      operator_id: operatorId.value,
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
    })
  } catch {
    cashSummary.value = null
  }
}

async function load() {
  loading.value = true
  try {
    const common = {
      keyword: keyword.value.trim(),
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      operator_id: operatorId.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    }
    if (tab.value === 'deposits') {
      const data = await recordApi.deposits({ ...common, reason: reason.value || undefined })
      entries.value = data.items
      total.value = data.total
      await loadCashSummary()
    } else {
      const data = await recordApi.sessions(common)
      sessions.value = data.items
      total.value = data.total
      cashSummary.value = null
    }
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

async function voidSession(row: SessionRow) {
  try {
    await ElMessageBox.confirm(
      `确定撤回「${row.name}」这一局？将删除该场次与它产生的茶水扣费，` +
        `退回 ${row.player_count} 名玩家的押金与局数（每人 ¥${formatCents(row.tea_fee_cents)}）。` +
        '只适用于刚开、且之后没再操作过这些玩家的局；不会生成任何加押/退押记录。',
      '撤回这一局',
      { confirmButtonText: '确认撤回', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  await sessionApi.void(row.id)
  ElMessage.success('已撤回这一局')
  await load()
  app.notifySessionCreated()
}

function onTabChange() {
  reload()
}

watch(
  () => route.query.keyword,
  (value) => {
    const text = typeof value === 'string' ? value : ''
    if (text === keyword.value) return
    keyword.value = text
    reload()
  },
)

onMounted(() => {
  if (typeof route.query.keyword === 'string') keyword.value = route.query.keyword
  void loadOperators()
  load()
})
</script>

<style scoped>
.small {
  font-size: 12px;
}

.cash-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 18px;
  margin-bottom: 10px;
  padding: 10px 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-bg-panel);
  font-size: 12.5px;
}

.cash-summary b {
  font-variant-numeric: tabular-nums;
}

.diff-in {
  color: var(--el-color-success);
}

.diff-out {
  color: var(--el-color-warning);
}

.panel {
  padding: 2px 0 0;
}

.nowrap {
  white-space: nowrap;
}

.record-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.record-card {
  padding: 12px 14px;
  background: var(--app-bg-panel);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.record-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 2px;
}

.record-card-head :deep(.amount) {
  font-weight: 600;
  white-space: nowrap;
}

.record-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.record-card-players {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--app-border);
  font-size: 12px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.record-card-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

.players {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}

.page.embedded {
  max-width: none;
  padding: 0;
}
</style>
