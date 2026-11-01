<template>
  <el-drawer
    :model-value="modelValue"
    :title="player ? `${player.game_id} 的流水` : '押金流水'"
    size="660px"
    @update:model-value="close"
  >
    <div v-if="player" class="summary">
      <div>
        <span class="muted">当前押金</span>
        <DepositBadge :cents="player.deposit_cents" :level="player.deposit_level" />
      </div>
      <div><span class="muted">总局数</span><b>{{ player.games_played }}</b></div>
      <div><span class="muted">累计充值</span><b>¥{{ formatCents(totalIn) }}</b></div>
      <div><span class="muted">累计支出</span><b>¥{{ formatCents(totalOut) }}</b></div>
    </div>

    <el-table :data="rows" v-loading="loading" size="small" height="calc(100vh - 220px)">
      <el-table-column label="时间" width="132">
        <template #default="{ row }">
          <span class="muted">{{ formatShort(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="原因" min-width="156">
        <template #default="{ row }">
          <div class="cell-main">{{ row.reason_label }}</div>
          <div v-if="row.note" class="cell-sub">{{ row.note }}</div>
        </template>
      </el-table-column>
      <el-table-column label="变动" width="98" align="right">
        <template #default="{ row }">
          <MoneyText :cents="row.signed_amount_cents" change />
        </template>
      </el-table-column>
      <el-table-column label="变动后" width="98" align="right">
        <template #default="{ row }">
          <span class="mono">¥{{ formatCents(row.balance_after_cents) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作人" width="88">
        <template #default="{ row }">
          <span class="muted">{{ row.operator?.display_name || '-' }}</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        small
        @current-change="load"
      />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import { playerApi } from '@/api'
import type { LedgerEntryRow, PlayerRow } from '@/api/types'
import DepositBadge from '@/components/common/DepositBadge.vue'
import MoneyText from '@/components/common/MoneyText.vue'
import { formatShort } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
  player: PlayerRow | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const rows = ref<LedgerEntryRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const totalIn = ref(0)
const totalOut = ref(0)

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible || !props.player) return
    page.value = 1
    await load()
    try {
      const detail = await playerApi.get(props.player.id)
      totalIn.value = detail.total_in_cents || 0
      totalOut.value = detail.total_out_cents || 0
    } catch {
      totalIn.value = 0
      totalOut.value = 0
    }
  },
)

async function load() {
  if (!props.player) return
  loading.value = true
  try {
    const data = await playerApi.ledger(props.player.id, {
      page: page.value,
      page_size: pageSize,
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<style scoped>
.summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #14161c;
  border: 1px solid #20242d;
  border-radius: 9px;
  font-size: 12.5px;
}

.summary div {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.summary b {
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 10px;
}
</style>
