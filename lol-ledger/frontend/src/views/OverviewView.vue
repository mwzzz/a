<template>
  <div v-loading="loading && !!data" element-loading-text="正在刷新…" class="page">
    <div class="page-head">
      <span class="page-title">工作台</span>
      <span class="page-sub">今日经营、押金与待处理事项</span>
      <div class="spacer"></div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <div v-if="error" class="panel state-panel">
      <div class="state-title">数据暂不可用</div>
      <div class="state-desc muted">工作台数据没有加载成功，请检查网络或服务后重试。</div>
      <el-button type="primary" :loading="loading" @click="load">重试</el-button>
    </div>
    <div
      v-else-if="loading && !data"
      v-loading="true"
      element-loading-text="正在加载工作台数据…"
      class="panel state-panel state-loading"
    >
      <div class="state-title">正在加载工作台数据…</div>
    </div>
    <template v-else-if="data">
    <div class="hero panel">
      <div class="hero-head">
        <div>
          <div class="hero-title">今日经营</div>
          <div class="muted small">{{ data?.date || '' }}</div>
        </div>
        <div class="hero-actions">
          <el-button type="primary" :icon="VideoPlay" @click="openSession">开一局</el-button>
          <el-button :icon="Wallet" @click="goPlayers">加押金</el-button>
          <el-button :icon="TrendCharts" @click="router.push({ name: 'summary' })">看汇总</el-button>
        </div>
      </div>
      <div class="hero-stats">
        <div class="hero-stat">
          <span>今日差额</span>
          <b :class="(data?.today.cash_diff_cents || 0) < 0 ? 'diff-out' : 'diff-in'">
            ¥{{ formatCents(data?.today.cash_diff_cents || 0) }}
          </b>
          <small>{{ (data?.today.cash_diff_cents || 0) < 0 ? '店长应补' : '店员应交' }}</small>
        </div>
        <div class="hero-stat">
          <span>今日茶水</span>
          <b>¥{{ formatCents(data?.today.tea_cents || 0) }}</b>
          <small>按本日场次累计</small>
        </div>
        <div class="hero-stat">
          <span>玩家押金总额</span>
          <b>¥{{ formatCents(data?.total_deposit_cents || 0) }}</b>
          <small>
            当前在库押金
            <template v-if="(data?.total_bonus_cents || 0) > 0">
              · 赠金 ¥{{ formatCents(data?.total_bonus_cents) }}
            </template>
          </small>
        </div>
        <div
          class="hero-stat clickable"
          :class="{ alert: (data?.low_deposit_count || 0) > 0 }"
          @click="goPlayers"
        >
          <span>押金不足</span>
          <b :class="{ 'diff-out': (data?.low_deposit_count || 0) > 0 }">
            {{ data?.low_deposit_count || 0 }} 人
          </b>
          <small>低于 ¥{{ formatCents(data?.deposit_low_cents || 3000) }}，点此去催补</small>
        </div>
      </div>
    </div>

    <div class="work-grid">
      <div class="panel block">
        <div class="section-head">
          <div class="section-title">今日操作人</div>
          <span class="muted small">按开局数排序</span>
          <div class="spacer"></div>
          <el-button link type="primary" @click="router.push({ name: 'summary' })">
            查看汇总
          </el-button>
        </div>
        <div v-if="operatorRanking.length" class="op-list">
          <div class="op-head">
            <span></span>
            <span>操作人</span>
            <span class="op-cell">局数</span>
            <span class="op-cell">茶水</span>
            <span class="op-cell">现金差额</span>
          </div>
          <div
            v-for="(row, index) in operatorRanking"
            :key="row.user?.id || index"
            class="op-row"
          >
            <span class="op-rank">{{ index + 1 }}</span>
            <span class="op-name">{{ row.user?.display_name || row.user?.username || '未知' }}</span>
            <span class="op-cell">{{ row.session_count }}</span>
            <span class="op-cell">¥{{ formatCents(row.tea_cents) }}</span>
            <span class="op-cell" :class="row.cash_diff_cents < 0 ? 'diff-out' : 'diff-in'">
              {{ row.cash_diff_cents < 0 ? '应补' : '应交' }}
              ¥{{ formatCents(Math.abs(row.cash_diff_cents)) }}
            </span>
          </div>
        </div>
        <div v-else class="empty-inline">今天还没有人开局</div>
      </div>

      <div class="panel block">
        <div class="section-head">
          <div class="section-title">待处理</div>
          <span class="muted small">需要店员行动的事项</span>
        </div>
        <div v-if="(data?.low_deposit_count || 0) > 0" class="todo-list">
          <div class="todo-item alert">
            <div>
              <b>{{ data?.low_deposit_count || 0 }} 个玩家押金不足</b>
              <span class="muted">
                低于 ¥{{ formatCents(data?.deposit_low_cents || 3000) }}，建议提醒补押金
              </span>
            </div>
            <el-button link type="primary" @click="goPlayers">去处理</el-button>
          </div>
        </div>
        <div v-else class="empty-inline">暂无待处理事项</div>
        <div class="quick-actions">
          <el-button :icon="Upload" @click="router.push({ name: 'players', query: { import: '1' } })">
            批量导入玩家
          </el-button>
          <el-button :icon="TrendCharts" @click="router.push({ name: 'reports' })">
            看报表
          </el-button>
        </div>
      </div>
    </div>

    <div class="panel desktop-only">
      <div class="recent-head">
        <div class="section-title">最近流水</div>
        <div class="spacer"></div>
        <el-button link type="primary" @click="router.push({ name: 'records' })">查看全部</el-button>
      </div>
      <el-table :data="data?.recent_records || []">
        <el-table-column label="时间" width="150">
          <template #default="{ row }">
            <span class="muted">{{ formatShort(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="玩家" min-width="150">
          <template #default="{ row }">{{ row.player.game_id }}</template>
        </el-table-column>
        <el-table-column label="变动" width="110" align="right">
          <template #default="{ row }">
            <MoneyText :cents="row.signed_amount_cents" change />
          </template>
        </el-table-column>
        <el-table-column label="变动后" width="110" align="right">
          <template #default="{ row }">
            <span class="mono muted">¥{{ formatCents(row.balance_after_cents) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="原因" min-width="200">
          <template #default="{ row }">
            <div class="cell-main">{{ row.reason_label }}</div>
            <div v-if="row.note" class="cell-sub">{{ row.note }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作人" width="100">
          <template #default="{ row }">
            <span class="muted">{{ row.operator?.display_name || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!loading && !data?.recent_records?.length" class="empty-hint">还没有流水</div>
    </div>

    <div class="panel mobile-only recent-mobile">
      <div class="recent-head">
        <div class="section-title">最近流水</div>
        <div class="spacer"></div>
        <el-button link type="primary" @click="router.push({ name: 'records' })">查看全部</el-button>
      </div>
      <div class="recent-cards">
        <div v-for="row in data?.recent_records || []" :key="row.id" class="recent-card">
          <div class="recent-card-head">
            <span class="cell-main">{{ row.player.game_id }}</span>
            <MoneyText :cents="row.signed_amount_cents" change />
          </div>
          <div class="cell-sub">
            {{ row.reason_label }}
            <template v-if="row.note"> · {{ row.note }}</template>
          </div>
          <div class="recent-card-meta">
            <span>{{ formatShort(row.created_at) }}</span>
            <span class="mono">余额 ¥{{ formatCents(row.balance_after_cents) }}</span>
            <span>{{ row.operator?.display_name || '-' }}</span>
          </div>
        </div>
        <div v-if="!loading && !data?.recent_records?.length" class="empty-hint">还没有流水</div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Refresh, TrendCharts, Upload, VideoPlay, Wallet } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { overviewApi } from '@/api'
import type { OverviewPayload } from '@/api/types'
import MoneyText from '@/components/common/MoneyText.vue'
import { useAppStore } from '@/stores/app'
import { formatShort } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const router = useRouter()
const app = useAppStore()
const data = ref<OverviewPayload | null>(null)
const loading = ref(true)
const error = ref(false)
let loadSeq = 0

function openSession() {
  router.push({ name: 'summary', query: { new: '1' } })
}

function goPlayers() {
  router.push({ name: 'players' })
}

const operatorRanking = computed(() =>
  (data.value?.today_operators || [])
    .filter((row) => row.session_count > 0)
    .sort((a, b) => {
      if (b.session_count !== a.session_count) return b.session_count - a.session_count
      if (b.tea_cents !== a.tea_cents) return b.tea_cents - a.tea_cents
      const left = a.user?.display_name || a.user?.username || ''
      const right = b.user?.display_name || b.user?.username || ''
      return left.localeCompare(right)
    }),
)

async function load() {
  const seq = ++loadSeq
  loading.value = true
  error.value = false
  try {
    const payload = await overviewApi.get()
    if (seq !== loadSeq) return
    data.value = payload
    void app.refreshToday()
  } catch {
    if (seq !== loadSeq) return
    error.value = true
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.two-col {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 12px;
  margin-bottom: 14px;
}

.block {
  padding: 16px 18px;
}

.mini-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px 12px;
}

.mini {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 9px 11px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.mini span {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
}

.mini b {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.batch-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13.5px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-success);
}

.custody-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 12.5px;
}

.custody-line b {
  font-size: 16px;
  color: var(--el-color-success);
  font-variant-numeric: tabular-nums;
}

.op-list {
  margin-top: 4px;
}

.op-head,
.op-row {
  display: grid;
  grid-template-columns: 24px minmax(80px, 1fr) 48px 76px 112px;
  align-items: center;
  gap: 8px;
}

.op-head {
  padding: 0 0 6px;
  border-bottom: 1px solid var(--app-border);
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
}

.op-row {
  padding: 7px 0;
  font-size: 12.5px;
}

.op-row + .op-row {
  border-top: 1px solid var(--app-border);
}

.op-rank {
  color: var(--app-text-muted);
  font-variant-numeric: tabular-nums;
}

.op-name {
  min-width: 0;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.op-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.diff-out {
  color: var(--el-color-danger);
}

.diff-in {
  color: var(--el-color-success);
}

.small {
  font-size: 12px;
}

.go {
  margin-top: 14px;
}

.no-batch {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  padding: 18px 0 8px;
}

.recent-head {
  display: flex;
  align-items: center;
  padding: 14px 16px 0;
}

.recent-head .section-title {
  margin: 0;
}

.recent-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 14px 14px;
}

.recent-card {
  padding: 10px 12px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.recent-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.recent-card-head :deep(.amount) {
  font-weight: 600;
  white-space: nowrap;
}

.recent-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.hero {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 22px;
  margin-bottom: 12px;
  background: linear-gradient(135deg, var(--app-bg-panel), var(--app-bg-subtle));
}

.hero-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.hero-title {
  font-size: 15px;
  font-weight: 600;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.hero-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-bg-subtle);
}

.hero-stat > span {
  font-size: 12px;
  color: var(--app-text-muted);
}

.hero-stat b {
  font-size: 24px;
  letter-spacing: -0.3px;
  font-variant-numeric: tabular-nums;
}

.hero-stat small {
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.hero-stat.clickable {
  cursor: pointer;
}

.hero-stat.alert {
  background: var(--app-warning-soft);
  border-color: rgba(230, 162, 60, 0.28);
}

.hero-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.work-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 14px;
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

.empty-inline {
  padding: 14px 0 4px;
  font-size: 12.5px;
  color: var(--app-text-muted);
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-bg-subtle);
}

.todo-item > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12.5px;
}

.todo-item b {
  font-weight: 600;
}

.todo-item .muted {
  font-size: 11.5px;
}

.todo-item.alert {
  background: var(--app-warning-soft);
  border-color: rgba(230, 162, 60, 0.28);
}

.quick-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .hero {
    gap: 14px;
    padding: 16px;
  }

  .hero-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-stat b {
    font-size: 20px;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .work-grid {
    grid-template-columns: 1fr;
  }

  .op-head,
  .op-row {
    grid-template-columns: 22px minmax(72px, 1fr) 44px 96px;
    gap: 6px;
    font-size: 11.5px;
  }

  .op-head span:nth-child(4),
  .op-row .op-cell:nth-child(4) {
    display: none;
  }
}
.state-panel {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 24px;
}

.state-title {
  font-size: 16px;
  font-weight: 600;
}

.state-desc {
  font-size: 12.5px;
}

.state-loading {
  min-height: 180px;
  align-items: center;
  justify-content: center;
  text-align: center;
}
</style>
