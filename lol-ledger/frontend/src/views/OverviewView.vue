<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">工作台</span>
      <span class="page-sub">这一班的现金、营业和待处理事项</span>
      <div class="spacer"></div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div v-loading="loading" class="hero panel">
      <div class="hero-main">
        <div class="hero-top">
          <StatusTag type="success" :label="`今天 ${data?.today.session_count || 0} 局`" />
          <span class="muted">{{ data?.date || '' }}</span>
        </div>
        <div class="hero-cash">
          <span class="hero-label">玩家押金总额</span>
          <b>¥{{ formatCents(data?.total_deposit_cents || 0) }}</b>
        </div>
        <div class="hero-meta">
          <span>{{ data?.player_count || 0 }} 个在用玩家</span>
          <span class="sep">·</span>
          <span>今日茶水 <b>¥{{ formatCents(data?.today.tea_cents || 0) }}</b></span>
          <span class="sep">·</span>
          <span>今日差额 <b>¥{{ formatCents(data?.today.cash_diff_cents || 0) }}</b></span>
        </div>
      </div>
      <div class="hero-actions">
        <el-button type="primary" :icon="VideoPlay" @click="openSession">开一局</el-button>
        <el-button :icon="Wallet" @click="goPlayers">加押金</el-button>
        <el-button :icon="TrendCharts" @click="router.push({ name: 'summary' })">看汇总</el-button>
      </div>
    </div>

    <div class="metric-grid">
      <StatCard
        label="今日茶水"
        :value="'¥' + formatCents(data?.today.tea_cents || 0)"
        tone="good"
        :hint="`${data?.today.session_count || 0} 局 · ${data?.today.player_times || 0} 人次`"
      />
      <StatCard
        label="今日收押金"
        :value="'¥' + formatCents(data?.today.add_deposit_cents || 0)"
        :hint="`退押金 ¥${formatCents(data?.today.refund_cents || 0)}`"
      />
      <StatCard
        label="押金不足"
        :value="`${data?.low_deposit_count || 0} 人`"
        :tone="(data?.low_deposit_count || 0) > 0 ? 'bad' : 'default'"
        :hint="`低于 ¥${formatCents(data?.deposit_low_cents || 3000)}，点此去催补`"
        @click="goPlayers"
      />
    </div>

    <div class="work-grid">
      <div class="panel block">
        <div class="section-head">
          <div class="section-title">今日概览</div>
          <span class="muted small">
            {{
              data?.dividend_mode === 'fixed'
                ? `每局 ¥${formatCents(data?.dividend_fixed_cents || 0)} 分红`
                : `茶水分红 ${data?.dividend_rate_percent || 0}%`
            }}
          </span>
          <div class="spacer"></div>
          <el-button link type="primary" @click="router.push({ name: 'summary' })">
            操作人汇总
          </el-button>
        </div>
        <div class="mini-grid">
          <div class="mini"><span>局数</span><b>{{ data?.today.session_count || 0 }}</b></div>
          <div class="mini"><span>人次</span><b>{{ data?.today.player_times || 0 }}</b></div>
          <div class="mini"><span>茶水</span><b>¥{{ formatCents(data?.today.tea_cents || 0) }}</b></div>
          <div class="mini"><span>分红</span><b>¥{{ formatCents(data?.today.dividend_cents || 0) }}</b></div>
        </div>
        <div class="mini-grid">
          <div class="mini"><span>收押金</span><b>¥{{ formatCents(data?.today.add_deposit_cents || 0) }}</b></div>
          <div class="mini"><span>退押金</span><b>¥{{ formatCents(data?.today.refund_cents || 0) }}</b></div>
          <div class="mini"><span>差额</span><b>¥{{ formatCents(data?.today.cash_diff_cents || 0) }}</b></div>
          <div class="mini"><span>押金余额</span><b>¥{{ formatCents(data?.total_deposit_cents || 0) }}</b></div>
        </div>
        <div class="empty-inline">
          差额 = 收押金 − 退押金：正数是店员该交给店长的现金，负数是店长该补给店员的。
        </div>
      </div>

      <div class="panel block">
        <div class="section-title">待处理</div>
        <div class="todo-list">
          <div class="todo-item" :class="{ alert: (data?.low_deposit_count || 0) > 0 }">
            <div>
              <b>{{ data?.low_deposit_count || 0 }} 个玩家押金不足</b>
              <span class="muted">低于 ¥{{ formatCents(data?.deposit_low_cents || 3000) }}</span>
            </div>
            <el-button link type="primary" @click="goPlayers">去处理</el-button>
          </div>
          <div class="todo-item">
            <div>
              <b>今日收押金 ¥{{ formatCents(data?.today.add_deposit_cents || 0) }}</b>
              <span class="muted">退押金 ¥{{ formatCents(data?.today.refund_cents || 0) }}</span>
            </div>
            <el-button link type="primary" @click="goPlayers">记一笔</el-button>
          </div>
          <div class="todo-item">
            <div>
              <b>今日已开 {{ data?.today.session_count || 0 }} 局</b>
              <span class="muted">
                茶水 ¥{{ formatCents(data?.today.tea_cents || 0) }}，分红
                ¥{{ formatCents(data?.today.dividend_cents || 0) }}
              </span>
            </div>
            <el-button link type="primary" @click="router.push({ name: 'summary' })">去对账</el-button>
          </div>
        </div>
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
  </div>
</template>

<script setup lang="ts">
import { Refresh, TrendCharts, Upload, VideoPlay, Wallet } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { overviewApi } from '@/api'
import type { OverviewPayload } from '@/api/types'
import MoneyText from '@/components/common/MoneyText.vue'
import StatCard from '@/components/common/StatCard.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { useAppStore } from '@/stores/app'
import { formatShort } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const router = useRouter()
const app = useAppStore()
const data = ref<OverviewPayload | null>(null)
const loading = ref(false)

function openSession() {
  router.push({ name: 'summary', query: { new: '1' } })
}

function goPlayers() {
  router.push({ name: 'players' })
}

async function load() {
  loading.value = true
  try {
    data.value = await overviewApi.get()
    void app.refreshToday()
  } finally {
    loading.value = false
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
  margin-top: 12px;
  border-top: 1px solid var(--app-border);
  padding-top: 8px;
}

.op-head {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.op-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  font-size: 12.5px;
}

.op-name {
  min-width: 80px;
  font-weight: 600;
}

.op-row .div {
  margin-left: auto;
  color: var(--el-color-warning);
  font-variant-numeric: tabular-nums;
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
  align-items: center;
  gap: 24px;
  padding: 20px 22px;
  margin-bottom: 12px;
  background: linear-gradient(135deg, var(--app-bg-panel), var(--app-bg-subtle));
}

.hero-main {
  flex: 1;
  min-width: 0;
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.hero-cash {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.hero-label {
  font-size: 12.5px;
  color: var(--app-text-muted);
}

.hero-cash b {
  font-size: 30px;
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 6px;
  font-size: 12.5px;
  color: var(--app-text-muted);
}

.hero-meta b {
  color: var(--el-text-color-regular);
}

.hero-meta .sep {
  color: var(--app-border-strong);
}

.hero-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
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
    flex-direction: column;
    align-items: stretch;
    gap: 14px;
    padding: 16px;
  }

  .hero-cash b {
    font-size: 26px;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .work-grid {
    grid-template-columns: 1fr;
  }

  .mini-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
