<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">账本</span>
      <span class="page-sub">按班次汇总，数字来自已保存的快照</span>
      <div class="spacer"></div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="panel">
      <el-table v-loading="loading" :data="batches">
        <el-table-column label="批次" min-width="220">
          <template #default="{ row }">
            <div class="cell-main" :title="`批次 #${row.id}`">
              {{ row.label || formatBatchTime(row) }}
            </div>
            <div v-if="row.label" class="cell-sub">{{ formatBatchTime(row) }}</div>
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
        <el-table-column label="划转" width="130" align="right">
          <template #default="{ row }">
            <span class="mono muted">
              {{ row.summary.transfer_count }} 笔 / ¥{{ formatCents(row.summary.transfer_out_total_cents) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="玩家押金余额" width="140" align="right">
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
      口径：划转只统计转出方（两边金额相等方向相反，相加恒为 0）；玩家押金余额是交班那一刻全店押金合计；
      期初 = 期末 − 净变动。
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
import { Refresh } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

import { batchApi, downloadBatchCsv } from '@/api'
import type { BatchRow } from '@/api/types'
import { formatBatchTime } from '@/utils/batch'
import { formatCents } from '@/utils/money'

const batches = ref<BatchRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

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

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}
</style>
