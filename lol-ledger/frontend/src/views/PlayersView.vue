<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">玩家</span>
      <span class="page-sub">
        共 {{ total }} 人 · 总押金 ¥{{ formatCents(totalDeposit) }}
        <template v-if="totalBonus > 0">· 赠金 ¥{{ formatCents(totalBonus) }}</template>
      </span>

      <div v-if="!auth.isSuperadmin" class="my-shift">
        <template v-if="!clockedIn">
          <el-button size="small" type="primary" plain :icon="AlarmClock" @click="onClockIn">
            上班打卡
          </el-button>
          <span class="ms-hint muted small">打卡后这里显示你这一班的场次 / 茶水 / 差额 / 分红</span>
        </template>
        <template v-else>
          <div class="ms-head">
            <span class="ms-label">
              我的本班
              <span class="muted">自 {{ shiftStartText ? formatClock(shiftStartText) : '--' }}</span>
            </span>
            <el-button link type="primary" size="small" @click="onClockIn">重新打卡</el-button>
            <el-button link size="small" :icon="Refresh" @click="loadMyShift">刷新</el-button>
          </div>
          <div class="ms-grid">
            <span>场次 <b>{{ myShift?.session_count ?? 0 }}</b></span>
            <span>人次 <b>{{ myShift?.player_times ?? 0 }}</b></span>
            <span>茶水 <b>¥{{ formatCents(myShift?.tea_cents ?? 0) }}</b></span>
            <span>收 <b>¥{{ formatCents(myShift?.add_deposit_cents ?? 0) }}</b></span>
            <span>退 <b>¥{{ formatCents(myShift?.refund_cents ?? 0) }}</b></span>
            <span>
              差额
              <b :class="(myShift?.cash_diff_cents ?? 0) < 0 ? 'diff-out' : 'diff-in'">
                ¥{{ formatCents(myShift?.cash_diff_cents ?? 0) }}
              </b>
            </span>
            <span>分红 <b class="div">¥{{ formatCents(myShift?.dividend_cents ?? 0) }}</b></span>
          </div>
          <div v-if="shiftStale" class="ms-hint muted small">
            打卡已超过 24 小时，数字只算最近 24 小时，建议重新打卡
          </div>
        </template>
      </div>

      <div class="spacer"></div>
      <el-button :icon="Upload" @click="importVisible = true">批量导入</el-button>
      <el-button :icon="Download" :loading="exporting" @click="exportPlayers">
        导出玩家库
      </el-button>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增玩家</el-button>
    </div>

    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索游戏名、段位或备注"
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

      <el-select v-model="blacklisted" placeholder="全部玩家" style="width: 132px" @change="reload">
        <el-option label="全部玩家" value="" />
        <el-option label="仅黑名单" value="only" />
        <el-option label="非黑名单" value="normal" />
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
      <span class="muted small">低于 ¥{{ formatCents(lowCents) }} 算押金不足 · 超过 ¥{{ formatCents(highCents) }} 显示绿色</span>
    </div>

    <div class="panel desktop-only">
      <el-table
        v-loading="loading"
        :data="rows"
        row-key="id"
        @row-dblclick="openLedger"
      >
        <el-table-column label="游戏名" min-width="280">
          <template #default="{ row }">
            <div class="cell-main">
              {{ row.game_id }}
              <el-tag v-if="row.is_blacklisted" type="danger" size="small" effect="dark">黑名单</el-tag>
            </div>
            <div class="cell-sub">
              <span>创建者 {{ row.creator?.display_name || '-' }}</span>
              <span v-if="row.account"> · 段位 {{ row.account }}</span>
              <span v-if="row.remark"> · {{ row.remark }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="押金" width="190" align="right">
          <template #default="{ row }">
            <DepositBadge
              :cents="row.balance_cents"
              :deposit-cents="row.deposit_cents"
              :bonus-cents="row.bonus_cents"
              :level="row.deposit_level"
            />
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

        <el-table-column label="操作" width="320" align="right">
          <template #default="{ row }">
            <div class="ops">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="openDeposit(row, 'add')">加押金</el-button>
              <el-button link type="warning" @click="openDeposit(row, 'refund')">退押金</el-button>
              <el-button link type="primary" @click="openTransfer(row)">划押</el-button>
              <el-dropdown trigger="click" @command="(cmd: string) => onMoreCommand(cmd, row)">
                <el-button link type="info">
                  更多<el-icon class="more-caret"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="ledger">查看流水</el-dropdown-item>
                    <el-dropdown-item command="bonus">加赠金</el-dropdown-item>
                    <el-dropdown-item
                      v-if="auth.isAdmin && row.bonus_cents > 0"
                      command="delete-bonus"
                    >
                      删除赠金
                    </el-dropdown-item>
                    <el-dropdown-item command="blacklist">
                      {{ row.is_blacklisted ? '移出黑名单' : '拉黑' }}
                    </el-dropdown-item>
                    <el-dropdown-item v-if="auth.isAdmin" command="delete" divided>
                      删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
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

    <div class="mobile-only player-cards">
      <div v-for="row in rows" :key="row.id" class="player-card" @click="openLedger(row)">
        <div class="player-card-head">
          <div>
            <div class="player-name">
              {{ row.game_id }}
              <el-tag v-if="row.is_blacklisted" type="danger" size="small" effect="dark">黑名单</el-tag>
            </div>
            <div class="cell-sub">
              创建者 {{ row.creator?.display_name || '-' }} · {{ row.games_played }} 局
            </div>
          </div>
          <div class="player-deposit">
            <span class="muted">押金</span>
            <DepositBadge
              :cents="row.balance_cents"
              :deposit-cents="row.deposit_cents"
              :bonus-cents="row.bonus_cents"
              :level="row.deposit_level"
            />
          </div>
        </div>
        <div class="player-card-meta">
          <span>最后活动 {{ relative(row.last_active_at) }}</span>
          <span v-if="row.account">段位 {{ row.account }}</span>
          <span v-if="row.remark">{{ row.remark }}</span>
        </div>
        <div class="player-card-ops" @click.stop>
          <el-button size="small" @click="openDeposit(row, 'add')">加押金</el-button>
          <el-button size="small" @click="openDeposit(row, 'refund')">退押金</el-button>
          <el-button size="small" @click="openTransfer(row)">划押</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-dropdown trigger="click" @command="(cmd: string) => onMoreCommand(cmd, row)">
            <el-button size="small">
              更多<el-icon class="more-caret"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="ledger">查看流水</el-dropdown-item>
                <el-dropdown-item command="bonus">加赠金</el-dropdown-item>
                <el-dropdown-item
                  v-if="auth.isAdmin && row.bonus_cents > 0"
                  command="delete-bonus"
                >
                  删除赠金
                </el-dropdown-item>
                <el-dropdown-item command="blacklist">
                  {{ row.is_blacklisted ? '移出黑名单' : '拉黑' }}
                </el-dropdown-item>
                <el-dropdown-item v-if="auth.isAdmin" command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
      <div v-if="!loading && !rows.length" class="empty-hint">还没有玩家</div>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, prev, pager, next"
          small
          @current-change="load"
          @size-change="reload"
        />
      </div>
    </div>

    <PlayerFormDialog v-model="formVisible" :player="editing" @saved="onSaved" />
    <PlayerImportDialog v-model="importVisible" @saved="onSaved" />
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
    <PlayerLedgerDrawer v-model="ledgerVisible" :player="active" @changed="reload" />
  </div>
</template>

<script setup lang="ts">
import { AlarmClock, ArrowDown, Download, Plus, Refresh, Search, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { moneyApi, overviewApi, playerApi, settingsApi, summaryApi } from '@/api'
import type { PlayerRow, SummaryTotals } from '@/api/types'
import DepositBadge from '@/components/common/DepositBadge.vue'
import DepositDialog from '@/components/players/DepositDialog.vue'
import PlayerFormDialog from '@/components/players/PlayerFormDialog.vue'
import PlayerImportDialog from '@/components/players/PlayerImportDialog.vue'
import PlayerLedgerDrawer from '@/components/players/PlayerLedgerDrawer.vue'
import TransferDialog from '@/components/players/TransferDialog.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { formatClock, formatFull, relative } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const app = useAppStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const rows = ref<PlayerRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const keyword = ref(typeof route.query.keyword === 'string' ? route.query.keyword : '')
const level = ref('')
const sort = ref('last_active_desc')
const blacklisted = ref<'' | 'only' | 'normal'>('')
const loading = ref(false)

const totalDeposit = ref(0)
const totalBonus = ref(0)
const lowCents = ref(3000)
const highCents = ref(6000)
const lastTeaCents = ref(200)

const formVisible = ref(false)
const importVisible = ref(false)
const exporting = ref(false)
const depositVisible = ref(false)
const transferVisible = ref(false)
const ledgerVisible = ref(false)
const editing = ref<PlayerRow | null>(null)
const active = ref<PlayerRow | null>(null)
const depositMode = ref<'add' | 'refund' | 'bonus'>('add')

const defaultTransferCents = computed(() => lastTeaCents.value * 10)

// —— 我的本班（纯前端：打卡时间存 localStorage，按当前账号隔离）——
const clockedIn = ref(false)
const shiftStartText = ref<string | null>(null)
const shiftStale = ref(false)
const myShift = ref<SummaryTotals | null>(null)

const pad2 = (n: number) => String(n).padStart(2, '0')
function minuteText(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}
function shiftKey(): string | null {
  return auth.user ? `lol_shift_start_${auth.user.id}` : null
}
function readClockIn(): string | null {
  const k = shiftKey()
  if (!k) return null
  const v = localStorage.getItem(k)
  return v && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(v) ? v : null
}

async function loadMyShift() {
  const clockIn = readClockIn()
  if (!clockIn || !auth.user) {
    clockedIn.value = false
    shiftStartText.value = null
    myShift.value = null
    return
  }
  clockedIn.value = true
  // 防呆：窗口最多回溯 24 小时，避免忘打卡把数字虚高（正常班次不受影响）
  const floor = minuteText(new Date(Date.now() - 24 * 3600 * 1000))
  shiftStale.value = clockIn <= floor
  const start = clockIn > floor ? clockIn : floor
  const end = minuteText(new Date())
  shiftStartText.value = start
  try {
    const data = await summaryApi.operators(start, end)
    const me = data.rows.find((r) => r.user?.id === auth.user?.id)
    myShift.value = me
      ? {
          session_count: me.session_count,
          player_times: me.player_times,
          tea_cents: me.tea_cents,
          add_deposit_cents: me.add_deposit_cents,
          refund_cents: me.refund_cents,
          cash_diff_cents: me.cash_diff_cents,
          dividend_cents: me.dividend_cents,
        }
      : {
          session_count: 0,
          player_times: 0,
          tea_cents: 0,
          add_deposit_cents: 0,
          refund_cents: 0,
          cash_diff_cents: 0,
          dividend_cents: 0,
        }
  } catch {
    myShift.value = null
  }
}

function onClockIn() {
  const k = shiftKey()
  if (!k) return
  localStorage.setItem(k, minuteText(new Date()))
  void loadMyShift()
}

let timer: number | undefined

async function load() {
  loading.value = true
  try {
    const data = await playerApi.list({
      keyword: keyword.value.trim(),
      level: level.value || undefined,
      sort: sort.value,
      blacklisted:
        blacklisted.value === 'only'
          ? true
          : blacklisted.value === 'normal'
            ? false
            : undefined,
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
    totalBonus.value = data.total_bonus_cents || 0
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

async function exportPlayers() {
  exporting.value = true
  try {
    const { blob, filename } = await playerApi.exportFile()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch {
    /* 错误提示由 axios 拦截器统一处理 */
  } finally {
    exporting.value = false
  }
}

function openCreate() {
  editing.value = null
  formVisible.value = true
}

function openEdit(row: PlayerRow) {
  editing.value = row
  formVisible.value = true
}

function openDeposit(row: PlayerRow, mode: 'add' | 'refund' | 'bonus') {
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

function onMoreCommand(cmd: string, row: PlayerRow) {
  if (cmd === 'ledger') openLedger(row)
  else if (cmd === 'bonus') openDeposit(row, 'bonus')
  else if (cmd === 'delete-bonus') deleteBonus(row)
  else if (cmd === 'blacklist') toggleBlacklist(row)
  else if (cmd === 'delete') remove(row)
}

function onSaved() {
  reload()
  loadSummary()
  loadMyShift()
}

function onPlayerChanged(player: PlayerRow) {
  const index = rows.value.findIndex((item) => item.id === player.id)
  if (index >= 0) rows.value[index] = player
  loadSummary()
  loadMyShift()
}

async function toggleBlacklist(row: PlayerRow) {
  const next = !row.is_blacklisted
  try {
    await ElMessageBox.confirm(
      next
        ? `将「${row.game_id}」加入黑名单？加入后不能开游戏。`
        : `将「${row.game_id}」移出黑名单？`,
      next ? '加入黑名单' : '移出黑名单',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  await playerApi.update(row.id, { is_blacklisted: next })
  ElMessage.success(next ? '已加入黑名单' : '已移出黑名单')
  reload()
}

async function deleteBonus(row: PlayerRow) {
  const cents = row.bonus_cents || 0
  if (cents <= 0) {
    ElMessage.warning('该玩家当前没有赠金')
    return
  }
  let note = ''
  try {
    const result = await ElMessageBox.prompt(
      `将删除「${row.game_id}」全部剩余赠金 ¥${formatCents(cents)}` +
        '（只清赠金、不动现金押金）。常用于误把加押金点成加赠金、且已被茶水消耗无法单笔撤销的收尾。请填写原因。',
      '删除赠金',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        inputPlaceholder: '删除原因（记入流水备注）',
        type: 'warning',
      },
    )
    note = (result.value || '').trim()
  } catch {
    return
  }
  const res = await moneyApi.deleteBonus(row.id, note)
  onPlayerChanged(res.player)
  ElMessage.success('已删除该玩家剩余赠金')
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
  () => route.query.keyword,
  (value) => {
    const text = typeof value === 'string' ? value : ''
    if (text !== keyword.value) keyword.value = text
  },
)

function handleQueryAction() {
  if (route.query.import === '1') {
    importVisible.value = true
    router.replace({ name: 'players' })
  }
}

watch(
  () => route.query.import,
  () => handleQueryAction(),
)

// 全局「开一局」弹窗创建场次后，玩家余额/本班统计会变，这里原地刷新
watch(
  () => app.sessionTick,
  () => {
    void load()
    void loadSummary()
    void loadMyShift()
  },
)

onMounted(async () => {
  await Promise.all([load(), loadSummary(), loadMyShift()])
  try {
    const settings = await settingsApi.get()
    lastTeaCents.value = settings.last_tea_cents
  } catch {
    /* 忽略 */
  }
  handleQueryAction()
})
</script>

<style scoped>
.small {
  font-size: 12px;
}

.my-shift {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-left: 18px;
  padding: 6px 12px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  background: var(--app-bg-panel);
}

.ms-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ms-label {
  font-size: 13px;
  font-weight: 600;
}

.ms-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 14px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.ms-grid b {
  font-variant-numeric: tabular-nums;
  color: var(--app-text);
}

.ms-hint {
  font-size: 11px;
}

.div {
  color: var(--el-color-primary);
}

.diff-in {
  color: var(--el-color-success);
}

.diff-out {
  color: var(--el-color-warning);
}

.ops {
  display: flex;
  align-items: center;
  gap: 2px;
  justify-content: flex-end;
}

.more-caret {
  margin-left: 2px;
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

.player-card {
  padding: 12px 14px;
  background: var(--app-bg-panel);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.player-card + .player-card {
  margin-top: 8px;
}

.player-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.player-name {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 2px;
}

.player-deposit {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: 11px;
  white-space: nowrap;
}

.player-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.player-card-ops {
  display: flex;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.player-card-ops :deep(.el-button) {
  flex: 1;
  margin-left: 0;
}
</style>
