<template>
  <div class="page">
    <div class="page-head">
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
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        style="width: 260px"
        @change="reload"
      />

      <el-select v-if="tab === 'deposits'" v-model="reason" placeholder="全部原因" style="width: 150px" @change="reload">
        <el-option label="全部原因" value="" />
        <el-option label="正常扣押" value="normal_deduct" />
        <el-option label="手动扣押" value="manual_deduct" />
        <el-option label="加押金" value="add_deposit" />
        <el-option label="退押金" value="refund" />
        <el-option label="划押转出" value="transfer_out" />
        <el-option label="划押转入" value="transfer_in" />
      </el-select>

      <el-button :icon="Refresh" @click="reload">刷新</el-button>
      <div class="spacer"></div>
      <span class="muted small">共 {{ total }} 条</span>
    </div>

    <el-tabs v-model="tab" @tab-change="onTabChange">
      <el-tab-pane label="押金记录" name="deposits">
        <div class="panel">
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
            <el-table-column label="变动后余额" width="120" align="right">
              <template #default="{ row }">
                <span class="mono muted">¥{{ formatCents(row.balance_after_cents) }}</span>
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
      </el-tab-pane>

      <el-tab-pane label="场次记录" name="sessions">
        <div class="panel">
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
          </el-table>
          <div v-if="!loading && !sessions.length" class="empty-hint">没有记录</div>
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
import { Refresh, Search } from '@element-plus/icons-vue'
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { recordApi } from '@/api'
import type { LedgerEntryRow, SessionRow } from '@/api/types'
import MoneyText from '@/components/common/MoneyText.vue'
import { formatFull, formatShort } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const route = useRoute()

const tab = ref<'deposits' | 'sessions'>('deposits')
const keyword = ref('')
const dateRange = ref<[string, string] | null>(null)
const reason = ref('')
const entries = ref<LedgerEntryRow[]>([])
const sessions = ref<SessionRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const common = {
      keyword: keyword.value.trim(),
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      page: page.value,
      page_size: pageSize.value,
    }
    if (tab.value === 'deposits') {
      const data = await recordApi.deposits({ ...common, reason: reason.value || undefined })
      entries.value = data.items
      total.value = data.total
    } else {
      const data = await recordApi.sessions(common)
      sessions.value = data.items
      total.value = data.total
    }
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
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
  load()
})
</script>

<style scoped>
.small {
  font-size: 12px;
}

.panel {
  padding: 2px 0 0;
}

.nowrap {
  white-space: nowrap;
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
</style>
