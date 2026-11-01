<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">账本</span>
      <span class="page-sub">按班次对账，数字来自已保存的快照</span>
      <div class="spacer"></div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="panel">
      <el-table v-loading="loading" :data="batches">
        <el-table-column label="批次" min-width="220">
          <template #default="{ row }">
            <div class="cell-main">{{ row.label || `批次 #${row.id}` }}</div>
            <div class="cell-sub">{{ row.display_label }}</div>
          </template>
        </el-table-column>
        <el-table-column label="局数" width="72" align="right">
          <template #default="{ row }"><span class="mono">{{ row.summary.session_count }}</span></template>
        </el-table-column>
        <el-table-column label="人次" width="72" align="right">
          <template #default="{ row }"><span class="mono">{{ row.summary.player_times }}</span></template>
        </el-table-column>
        <el-table-column label="茶水" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">¥{{ formatCents(row.summary.tea_total_cents) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="加押金" width="116" align="right">
          <template #default="{ row }">
            <span class="mono in">+¥{{ formatCents(row.summary.add_total_cents) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="退押金" width="116" align="right">
          <template #default="{ row }">
            <span class="mono" :class="row.summary.refund_total_cents ? 'out' : 'muted'">
              {{ row.summary.refund_total_cents ? '-¥' + formatCents(row.summary.refund_total_cents) : '¥0.00' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="手动扣押" width="116" align="right">
          <template #default="{ row }">
            <span class="mono" :class="row.summary.deduct_total_cents ? 'out' : 'muted'">
              {{ row.summary.deduct_total_cents ? '-¥' + formatCents(row.summary.deduct_total_cents) : '¥0.00' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="划转" width="130" align="right">
          <template #default="{ row }">
            <span class="mono muted">
              {{ row.summary.transfer_count }} 笔 / ¥{{ formatCents(row.summary.transfer_out_total_cents) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="期末总押金" width="130" align="right">
          <template #default="{ row }">
            <b class="mono">¥{{ formatCents(row.summary.deposit_total_cents) }}</b>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="112" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="exportCsv(row)">导出 CSV</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!loading && !batches.length" class="empty-hint">还没有批次</div>
    </div>

    <div class="hint">
      口径：划转只统计转出方（两边金额相等方向相反，相加恒为 0）；期末总押金是交班那一刻全店押金合计；
      期初 = 期末 − 净变动。
    </div>

    <div class="panel check">
      <div class="check-head">
        <div>
          <div class="section-title">对账</div>
          <div class="muted small">
            校验「玩家押金 = 流水合计 = 最后一条余额」三件事是否一致
          </div>
        </div>
        <div class="spacer"></div>
        <el-button v-if="auth.isAdmin" type="primary" :loading="checking" @click="runCheck">
          立即对账
        </el-button>
        <span v-else class="muted small">只有管理员可以执行对账</span>
      </div>

      <div v-if="report" class="report" :class="report.ok ? 'ok' : 'bad'">
        <div class="report-line">
          <el-icon><CircleCheck v-if="report.ok" /><Warning v-else /></el-icon>
          <span v-if="report.ok">
            账实一致，共检查 {{ report.checked }} 个玩家，总押金 ¥{{ formatCents(report.total_deposit_cents) }}
          </span>
          <span v-else>
            发现 {{ report.problems.length }} 个异常，请立即检查
          </span>
        </div>
        <el-table v-if="!report.ok" :data="report.problems" size="small">
          <el-table-column prop="game_id" label="玩家" min-width="140" />
          <el-table-column label="记录的押金" width="130" align="right">
            <template #default="{ row }">¥{{ formatCents(row.stored_cents) }}</template>
          </el-table-column>
          <el-table-column label="流水合计" width="130" align="right">
            <template #default="{ row }">¥{{ formatCents(row.ledger_sum_cents) }}</template>
          </el-table-column>
          <el-table-column label="最后余额" width="130" align="right">
            <template #default="{ row }">¥{{ formatCents(row.last_balance_cents) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="load"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { CircleCheck, Refresh, Warning } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import { batchApi, downloadBatchCsv, overviewApi } from '@/api'
import type { BatchRow, ReconcilePayload } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatCents } from '@/utils/money'

const auth = useAuthStore()

const batches = ref<BatchRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const checking = ref(false)
const report = ref<ReconcilePayload | null>(null)

async function load() {
  loading.value = true
  try {
    const data = await batchApi.list({
      status: 'all',
      page: page.value,
      page_size: pageSize.value,
      include_sessions: false,
    })
    batches.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function runCheck() {
  checking.value = true
  try {
    report.value = await overviewApi.reconcile()
  } finally {
    checking.value = false
  }
}

async function exportCsv(batch: BatchRow) {
  try {
    await downloadBatchCsv(batch.id, batch.label || String(batch.id))
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(load)
</script>

<style scoped>
.small {
  font-size: 12px;
}

.in {
  color: var(--el-color-success);
}

.out {
  color: var(--el-color-danger);
}

.hint {
  margin: 10px 2px 16px;
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
}

.check {
  padding: 16px 18px;
}

.check-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.report {
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 12.5px;
}

.report.ok {
  background: rgba(62, 207, 142, 0.08);
  border: 1px solid rgba(62, 207, 142, 0.25);
  color: #8fe3bb;
}

.report.bad {
  background: rgba(255, 92, 92, 0.08);
  border: 1px solid rgba(255, 92, 92, 0.3);
  color: #ffb3b3;
}

.report-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report.bad .el-table {
  margin-top: 10px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}
</style>
