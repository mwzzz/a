<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">总览</span>
      <span class="page-sub">今天和这一班的情况</span>
      <div class="spacer"></div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div v-loading="loading" class="cards">
      <StatCard
        label="玩家押金余额"
        :value="'¥' + formatCents(data?.total_deposit_cents || 0)"
        :hint="`${data?.player_count || 0} 个在用玩家`"
      />
      <StatCard
        label="押金不足"
        :value="`${data?.low_deposit_count || 0} 人`"
        :tone="(data?.low_deposit_count || 0) > 0 ? 'bad' : 'default'"
        :hint="`低于 ¥${formatCents(data?.deposit_low_cents || 3000)} 需要催补`"
      />
      <StatCard
        label="本班茶水"
        :value="'¥' + formatCents(data?.open_batch?.summary.tea_total_cents || 0)"
        tone="good"
        :hint="`${data?.open_batch?.summary.session_count || 0} 局 · ${data?.open_batch?.summary.player_times || 0} 人次`"
      />
      <StatCard
        label="本班收押金"
        :value="'¥' + formatCents(data?.open_batch?.summary.add_total_cents || 0)"
        :hint="`退押金 ¥${formatCents(data?.open_batch?.summary.refund_total_cents || 0)}`"
      />
      <StatCard
        label="在库现金"
        :value="'¥' + formatCents(data?.custody.amount_cents || 0)"
        :hint="`保管人：${data?.custody.holder?.display_name || '未设置'}`"
      />
    </div>

    <div class="two-col">
      <div class="panel block">
        <div class="section-title">本班流水</div>
        <div class="mini-grid">
          <div class="mini"><span>局数</span><b>{{ data?.open_batch?.summary.session_count || 0 }}</b></div>
          <div class="mini"><span>人次</span><b>{{ data?.open_batch?.summary.player_times || 0 }}</b></div>
          <div class="mini"><span>茶水</span><b>¥{{ formatCents(data?.open_batch?.summary.tea_total_cents || 0) }}</b></div>
          <div class="mini"><span>收押金</span><b>¥{{ formatCents(data?.open_batch?.summary.add_total_cents || 0) }}</b></div>
          <div class="mini"><span>退押金</span><b>¥{{ formatCents(data?.open_batch?.summary.refund_total_cents || 0) }}</b></div>
          <div class="mini"><span>划转笔数</span><b>{{ data?.open_batch?.summary.transfer_count || 0 }}</b></div>
          <div class="mini"><span>划转金额</span><b>¥{{ formatCents(data?.open_batch?.summary.transfer_out_total_cents || 0) }}</b></div>
        </div>
        <div v-if="!data?.open_batch" class="muted small" style="margin-top: 10px">
          当前没有进行中的班次，本班统计从下一次开班开始。
        </div>
      </div>

      <div class="panel block">
        <div class="section-title">当前批次</div>
        <template v-if="data?.open_batch">
          <div class="batch-line">
            <span class="dot"></span>
            <b>{{ batchLabel }}</b>
            <span class="dim-tag">进行中</span>
          </div>
          <div class="custody-line">
            <span class="muted">在库现金</span>
            <b>¥{{ formatCents(data.custody.amount_cents) }}</b>
            <span class="muted">保管人 {{ data.custody.holder?.display_name || '未设置' }}</span>
          </div>
          <div class="mini-grid">
            <div class="mini"><span>局数</span><b>{{ data.open_batch.summary.session_count }}</b></div>
            <div class="mini"><span>人次</span><b>{{ data.open_batch.summary.player_times }}</b></div>
            <div class="mini"><span>茶水</span><b>¥{{ formatCents(data.open_batch.summary.tea_total_cents) }}</b></div>
            <div class="mini"><span>玩家押金余额</span><b>¥{{ formatCents(data.open_batch.summary.deposit_total_cents) }}</b></div>
          </div>
          <div v-if="data.open_batch.operators.length" class="op-list">
            <div class="op-head">
              操作人 · 分红 {{ data.open_batch.dividend_rate_percent }}%
            </div>
            <div v-for="op in data.open_batch.operators" :key="op.user?.id || 'unknown'" class="op-row">
              <span class="op-name">{{ op.user?.display_name || '未知' }}</span>
              <span class="muted">{{ op.session_count }} 局 · {{ op.player_times }} 人次</span>
              <span class="mono">茶 ¥{{ formatCents(op.tea_cents) }}</span>
              <b class="div">分红 ¥{{ formatCents(op.dividend_cents) }}</b>
            </div>
          </div>
          <el-button class="go" type="primary" plain @click="router.push({ name: 'batches' })">
            去看这一班的场次
          </el-button>
        </template>
        <template v-else>
          <div class="no-batch">
            <div class="muted">现在没有进行中的批次</div>
            <el-button type="primary" plain @click="router.push({ name: 'batches' })">去开班</el-button>
          </div>
        </template>
      </div>
    </div>

    <div class="panel">
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
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { overviewApi } from '@/api'
import type { OverviewPayload } from '@/api/types'
import MoneyText from '@/components/common/MoneyText.vue'
import StatCard from '@/components/common/StatCard.vue'
import { formatShort } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const router = useRouter()
const data = ref<OverviewPayload | null>(null)
const loading = ref(false)

const batchLabel = computed(() => {
  const batch = data.value?.open_batch
  if (!batch) return ''
  const time = formatShort(batch.opened_at)
  return batch.label || `${time} 开班`
})

async function load() {
  loading.value = true
  try {
    data.value = await overviewApi.get()
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
  background: #101319;
  border: 1px solid #1c2028;
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
  border-top: 1px solid #1c2028;
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
</style>
