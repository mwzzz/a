<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">玩家</span>
      <span class="page-sub">共 {{ total }} 人 · 总押金 ¥{{ formatCents(totalDeposit) }}</span>
      <div class="spacer"></div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增玩家</el-button>
    </div>

    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索游戏名、账号或备注"
        clearable
        style="width: 250px"
        @keyup.enter="reload"
        @clear="reload"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select v-model="level" placeholder="全部押金" style="width: 132px" @change="reload">
        <el-option label="全部押金" value="" />
        <el-option label="不足（红）" value="low" />
        <el-option label="偏低（黄）" value="warn" />
        <el-option label="充足（绿）" value="safe" />
      </el-select>

      <el-select v-model="sort" style="width: 150px" @change="reload">
        <el-option label="总局数 ↓" value="games_played_desc" />
        <el-option label="押金 ↓" value="deposit_desc" />
        <el-option label="押金 ↑" value="deposit_asc" />
        <el-option label="最后活动 ↓" value="last_active_desc" />
        <el-option label="游戏名 ↑" value="game_id_asc" />
      </el-select>

      <el-button :icon="Refresh" @click="reload">刷新</el-button>
      <div class="spacer"></div>
      <span class="muted small">低于 ¥{{ formatCents(lowCents) }} 红色 · 超过 ¥{{ formatCents(highCents) }} 绿色</span>
    </div>

    <div class="panel">
      <el-table
        v-loading="loading"
        :data="rows"
        row-key="id"
        @row-dblclick="openLedger"
      >
        <el-table-column label="游戏名" min-width="280">
          <template #default="{ row }">
            <div class="cell-main">{{ row.game_id }}</div>
            <div class="cell-sub">
              <span>创建者 {{ row.creator?.display_name || '-' }}</span>
              <span v-if="row.account"> · 账号 {{ row.account }}</span>
              <span v-if="row.remark"> · {{ row.remark }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="押金" width="120" align="right">
          <template #default="{ row }">
            <DepositBadge :cents="row.deposit_cents" :level="row.deposit_level" />
          </template>
        </el-table-column>

        <el-table-column label="总局数" width="86" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.games_played }}</span>
          </template>
        </el-table-column>

        <el-table-column label="最后活动" width="120">
          <template #default="{ row }">
            <el-tooltip :content="formatFull(row.last_active_at)" placement="top">
              <span class="muted">{{ relative(row.last_active_at) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="268" align="right">
          <template #default="{ row }">
            <div class="ops">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="openDeposit(row, 'add')">加押金</el-button>
              <el-button link type="warning" @click="openDeposit(row, 'deduct')">扣押金</el-button>
              <el-button link type="primary" @click="openTransfer(row)">划押</el-button>
              <el-button v-if="auth.isAdmin" link type="danger" @click="remove(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && !rows.length" class="empty-hint">还没有玩家，点右上角「新增玩家」开始</div>

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

    <PlayerFormDialog v-model="formVisible" :player="editing" @saved="onSaved" />
    <DepositDialog
      v-model="depositVisible"
      :player="active"
      :mode="depositMode"
      @saved="onPlayerChanged"
    />
    <TransferDialog
      v-model="transferVisible"
      :player="active"
      :default-amount-cents="defaultTransferCents"
      @saved="reload"
    />
    <PlayerLedgerDrawer v-model="ledgerVisible" :player="active" />
  </div>
</template>

<script setup lang="ts">
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { overviewApi, playerApi, settingsApi } from '@/api'
import type { PlayerRow } from '@/api/types'
import DepositBadge from '@/components/common/DepositBadge.vue'
import DepositDialog from '@/components/players/DepositDialog.vue'
import PlayerFormDialog from '@/components/players/PlayerFormDialog.vue'
import PlayerLedgerDrawer from '@/components/players/PlayerLedgerDrawer.vue'
import TransferDialog from '@/components/players/TransferDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { formatFull, relative } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const rows = ref<PlayerRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const level = ref('')
const sort = ref('games_played_desc')
const loading = ref(false)

const totalDeposit = ref(0)
const lowCents = ref(3000)
const highCents = ref(6000)
const lastTeaCents = ref(200)

const formVisible = ref(false)
const depositVisible = ref(false)
const transferVisible = ref(false)
const ledgerVisible = ref(false)
const editing = ref<PlayerRow | null>(null)
const active = ref<PlayerRow | null>(null)
const depositMode = ref<'add' | 'refund' | 'deduct'>('add')

const defaultTransferCents = computed(() => lastTeaCents.value * 10)

let timer: number | undefined

async function load() {
  loading.value = true
  try {
    const data = await playerApi.list({
      keyword: keyword.value.trim(),
      level: level.value || undefined,
      sort: sort.value,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const data = await overviewApi.get()
    totalDeposit.value = data.total_deposit_cents
    lowCents.value = data.deposit_low_cents
    highCents.value = data.deposit_high_cents
  } catch {
    /* 忽略 */
  }
}

function reload() {
  page.value = 1
  load()
}

function openCreate() {
  editing.value = null
  formVisible.value = true
}

function openEdit(row: PlayerRow) {
  editing.value = row
  formVisible.value = true
}

function openDeposit(row: PlayerRow, mode: 'add' | 'refund' | 'deduct') {
  active.value = row
  depositMode.value = mode
  depositVisible.value = true
}

function openTransfer(row: PlayerRow) {
  active.value = row
  transferVisible.value = true
}

function openLedger(row: PlayerRow) {
  active.value = row
  ledgerVisible.value = true
}

function onSaved() {
  reload()
  loadSummary()
}

function onPlayerChanged(player: PlayerRow) {
  const index = rows.value.findIndex((item) => item.id === player.id)
  if (index >= 0) rows.value[index] = player
  loadSummary()
}

async function remove(row: PlayerRow) {
  try {
    await ElMessageBox.confirm(
      `确定删除玩家「${row.game_id}」？押金必须为 0，历史流水会保留但不再显示。`,
      '删除玩家',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  await playerApi.remove(row.id)
  ElMessage.success('已删除')
  reload()
  loadSummary()
}

watch(keyword, () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(reload, 400)
})

watch(
  () => route.query.new,
  (value) => {
    if (value === '1') {
      openCreate()
      router.replace({ name: 'players' })
    }
  },
)

onMounted(async () => {
  await Promise.all([load(), loadSummary()])
  try {
    const settings = await settingsApi.get()
    lastTeaCents.value = settings.last_tea_cents
  } catch {
    /* 忽略 */
  }
  if (route.query.new === '1') {
    openCreate()
    router.replace({ name: 'players' })
  }
})
</script>

<style scoped>
.small {
  font-size: 12px;
}

.ops {
  display: flex;
  align-items: center;
  gap: 2px;
  justify-content: flex-end;
}

.ops :deep(.el-button) {
  padding: 2px 5px;
  font-size: 12.5px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 12px 14px;
}
</style>
