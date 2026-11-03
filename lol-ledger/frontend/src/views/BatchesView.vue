<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">场次管理</span>
      <span class="page-sub">
        共 {{ total }} 个批次
        <template v-if="current">
          · 当前批次进行中 · 在库 ¥{{ formatCents(custody?.amount_cents || 0) }} · 保管人
          {{ custody?.holder?.display_name || '未设置' }}
        </template>
      </span>
      <div class="spacer"></div>
      <el-button v-if="!current" type="primary" :icon="VideoPlay" @click="newBatchVisible = true">
        开班
      </el-button>
      <el-button v-else type="primary" :icon="Plus" @click="openNewSession">新增场次</el-button>
    </div>

    <div class="toolbar">
      <el-select v-model="status" style="width: 130px" @change="reload">
        <el-option label="全部批次" value="all" />
        <el-option label="进行中" value="open" />
        <el-option label="已结束" value="closed" />
      </el-select>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开班开始日期"
        end-placeholder="结束日期"
        :shortcuts="dateShortcuts"
        unlink-panels
        style="width: 280px"
        @change="reload"
      />
      <el-button :icon="Refresh" @click="reload">刷新</el-button>
      <div class="spacer"></div>
      <span class="muted small">点开一条场次可以看本局每个人的扣费明细</span>
    </div>

    <div v-loading="loading" class="batch-list">
      <section v-for="batch in batches" :key="batch.id" class="batch">
        <header class="batch-head" @click="app.toggleBatch(batch.id)">
          <el-icon class="chevron" :class="{ collapsed: app.isCollapsed(batch.id) }">
            <ArrowRight />
          </el-icon>
          <span class="batch-label" :title="`批次 #${batch.id}`">
            {{ batch.label || formatBatchTime(batch) }}
          </span>
          <span v-if="batch.label" class="batch-time">{{ formatBatchTime(batch) }}</span>

          <div class="spacer"></div>

          <span class="stat">局数 <b>{{ batch.summary.session_count }}</b></span>
          <span class="stat">人次 <b>{{ batch.summary.player_times }}</b></span>
          <span class="stat">茶水 <b>¥{{ formatCents(batch.summary.tea_total_cents) }}</b></span>
          <span class="stat">玩家押金余额 <b>¥{{ formatCents(batch.summary.deposit_total_cents) }}</b></span>

          <el-button
            v-if="batch.status === 'open'"
            size="small"
            class="close-btn"
            @click.stop="openClose(batch)"
          >
            交班
          </el-button>
          <el-button size="small" text class="csv-btn" @click.stop="exportCsv(batch)">
            导出
          </el-button>
        </header>

        <div v-if="!app.isCollapsed(batch.id)" class="batch-body">
          <div class="operator-panel">
            <div class="operator-head">
              <span>操作人统计</span>
              <span class="muted small">分红比例 {{ batch.dividend_rate_percent }}% · 只算茶水</span>
            </div>
            <div v-if="batch.operators.length" class="operator-table">
              <div class="operator-row operator-title">
                <span>操作人</span>
                <span>局数</span>
                <span>人次</span>
                <span>茶水</span>
                <span>分红</span>
              </div>
              <div v-for="op in batch.operators" :key="op.user?.id || 'unknown'" class="operator-row">
                <span class="operator-name">{{ op.user?.display_name || '未知' }}</span>
                <span class="mono">{{ op.session_count }}</span>
                <span class="mono">{{ op.player_times }}</span>
                <span class="mono">¥{{ formatCents(op.tea_cents) }}</span>
                <span class="mono operator-div">¥{{ formatCents(op.dividend_cents) }}</span>
              </div>
            </div>
            <div v-else class="muted small operator-empty">这个批次还没有场次</div>
          </div>

          <div v-if="batch.handover" class="handover">
            <span class="muted">交班交接：</span>
            茶水 ¥{{ formatCents(batch.handover.tea_cents) }} 上缴
            {{ batch.handover.tea_to?.display_name || '-' }}（{{ batch.handover.tea_method_label }}）；
            押金 ¥{{ formatCents(batch.handover.deposit_cents) }} 交给
            {{ batch.handover.deposit_to?.display_name || '-' }}（{{ batch.handover.deposit_method_label }}）
          </div>

          <div v-if="batch.sessions.length" class="session-head">
            <span>场次名称</span>
            <span>时间</span>
            <span>操作人</span>
            <span>人数</span>
            <span>创建者</span>
            <span></span>
          </div>

          <div v-for="session in batch.sessions" :key="session.id" class="session-block">
            <div class="session-row" @click="toggleSession(session.id)">
              <span class="s-name">{{ session.name }}</span>
              <span class="muted">{{ formatShort(session.played_at) }}</span>
              <span class="muted">{{ session.operator?.display_name || '-' }}</span>
              <span class="mono">{{ session.player_count }}人</span>
              <span class="muted">{{ session.creator?.display_name || '-' }}</span>
              <el-icon class="row-caret" :class="{ open: expanded.has(session.id) }">
                <ArrowRight />
              </el-icon>
            </div>
            <div v-if="expanded.has(session.id)" class="chips">
              <span v-for="player in session.players" :key="player.player_id" class="chip">
                {{ player.game_id }}
                <em>{{ formatCents(player.balance_after_cents) }}</em>
              </span>
              <span class="chip-note">每人扣 ¥{{ formatCents(session.tea_fee_cents) }}</span>
            </div>
          </div>

          <div v-if="!batch.sessions.length" class="empty-hint">这个批次还没有场次</div>

          <div v-if="batch.status === 'open'" class="add-session" @click="openNewSession">
            <el-icon><Plus /></el-icon>
            新增场次
          </div>
        </div>
      </section>

      <div v-if="!loading && !batches.length" class="panel empty-batch">
        <div class="empty-title">还没有批次</div>
        <div class="muted">先点「开班」，这一班的场次和押金变动都会记在里面，交班时自动对账。</div>
        <el-button type="primary" :icon="VideoPlay" @click="newBatchVisible = true">开班</el-button>
      </div>
    </div>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="reload"
      />
    </div>

    <NewBatchDialog v-model="newBatchVisible" @created="onBatchCreated" />
    <NewSessionDialog
      v-model="newSessionVisible"
      :batch-id="current?.id ?? null"
      :default-tea-cents="teaCents"
      @created="onSessionCreated"
    />
    <CloseBatchDialog v-model="closeVisible" :batch="closing" @closed="onClosed" />
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, Plus, Refresh, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { batchApi, downloadBatchCsv, settingsApi } from '@/api'
import type { BatchRow, CustodyInfo } from '@/api/types'
import CloseBatchDialog from '@/components/batches/CloseBatchDialog.vue'
import NewBatchDialog from '@/components/batches/NewBatchDialog.vue'
import NewSessionDialog from '@/components/batches/NewSessionDialog.vue'
import { useAppStore } from '@/stores/app'
import { formatBatchTime } from '@/utils/batch'
import { formatShort } from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const app = useAppStore()
const route = useRoute()
const router = useRouter()

const batches = ref<BatchRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const status = ref('all')
const dateRange = ref<[string, string] | null>(null)
const loading = ref(false)
const current = ref<BatchRow | null>(null)
const custody = ref<CustodyInfo | null>(null)
const teaCents = ref(200)

const dateShortcuts = [
  {
    text: '今天',
    value: () => {
      const today = new Date()
      return [today, today]
    },
  },
  {
    text: '昨天',
    value: () => {
      const end = new Date()
      end.setDate(end.getDate() - 1)
      return [new Date(end), end]
    },
  },
  {
    text: '近 7 天',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - 6)
      return [start, end]
    },
  },
  {
    text: '本月',
    value: () => {
      const end = new Date()
      return [new Date(end.getFullYear(), end.getMonth(), 1), end]
    },
  },
]

const expanded = ref(new Set<number>())

const newBatchVisible = ref(false)
const newSessionVisible = ref(false)
const closeVisible = ref(false)
const closing = ref<BatchRow | null>(null)

async function load() {
  loading.value = true
  try {
    const data = await batchApi.list({
      status: status.value,
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      page: page.value,
      page_size: pageSize.value,
      include_sessions: true,
    })
    batches.value = data.items
    total.value = data.total
    const payload = await batchApi.current()
    current.value = payload.batch
    custody.value = payload.custody
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function toggleSession(id: number) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function openNewSession() {
  if (!current.value) {
    ElMessage.warning('当前没有进行中的批次，请先开班')
    newBatchVisible.value = true
    return
  }
  newSessionVisible.value = true
}

function openClose(batch: BatchRow) {
  closing.value = batch
  closeVisible.value = true
}

async function onBatchCreated() {
  await load()
  ElMessage.success('已开班，现在可以新增场次了')
}

async function onSessionCreated(payload: { batchId: number }) {
  await load()
  const next = new Set(expanded.value)
  next.delete(payload.batchId)
  app.collapsed = app.collapsed.filter((id) => id !== payload.batchId)
  expanded.value = next
}

async function onClosed() {
  await load()
}

async function exportCsv(batch: BatchRow) {
  try {
    await downloadBatchCsv(batch.id, batch.label || String(batch.id))
  } catch {
    /* 拦截器已提示 */
  }
}

watch(
  () => route.query.new,
  (value) => {
    if (value === '1') {
      openNewSession()
      router.replace({ name: 'batches' })
    }
  },
)

onMounted(async () => {
  await load()
  try {
    const settings = await settingsApi.get()
    teaCents.value = settings.last_tea_cents
  } catch {
    /* 忽略 */
  }
  if (route.query.new === '1') {
    openNewSession()
    router.replace({ name: 'batches' })
  }
})
</script>

<style scoped>
.small {
  font-size: 12px;
}

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 80px;
}

.batch {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  overflow: hidden;
}

.batch-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  cursor: pointer;
  background: #12151b;
  border-bottom: 1px solid transparent;
  user-select: none;
}

.batch-head:hover {
  background: #151922;
}

.chevron {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  transform: rotate(90deg);
  transition: transform 0.15s ease;
}

.chevron.collapsed {
  transform: rotate(0deg);
}

.batch-label {
  font-weight: 600;
  font-size: 13.5px;
}

.batch-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  padding-left: 12px;
  margin-left: 2px;
  border-left: 1px solid #232833;
}

.stat b {
  margin-left: 4px;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.close-btn {
  margin-left: 4px;
}

.csv-btn {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.batch-body {
  padding: 4px 14px 12px;
}

.operator-panel {
  margin: 8px 0 10px;
  padding: 10px 12px;
  background: #101319;
  border: 1px solid #1c2028;
  border-radius: 8px;
}

.operator-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 7px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.operator-table {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.operator-row {
  display: grid;
  grid-template-columns: minmax(110px, 1.4fr) 60px 60px 100px 100px;
  gap: 10px;
  padding: 5px 6px;
  font-size: 12.5px;
  border-radius: 5px;
}

.operator-row:not(.operator-title):nth-child(even) {
  background: #141821;
}

.operator-title {
  color: var(--el-text-color-secondary);
  font-size: 11.5px;
}

.operator-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.operator-div {
  color: var(--el-color-warning);
}

.operator-empty {
  padding: 4px 6px;
}

.handover {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-left: 2px solid var(--el-color-success);
  background: rgba(62, 207, 142, 0.06);
  border-radius: 0 6px 6px 0;
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.7;
}

.session-head {
  display: grid;
  grid-template-columns: minmax(180px, 1.6fr) 110px 90px 70px 90px 24px;
  gap: 10px;
  padding: 8px 10px;
  font-size: 11.5px;
  color: #6f7787;
  letter-spacing: 0.3px;
  border-bottom: 1px solid #1c2028;
}

.session-block + .session-block {
  border-top: 1px solid #171b22;
}

.session-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.6fr) 110px 90px 70px 90px 24px;
  gap: 10px;
  align-items: center;
  padding: 9px 10px;
  font-size: 12.5px;
  cursor: pointer;
  border-radius: 6px;
}

.session-row:hover {
  background: #161a22;
}

.s-name {
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-caret {
  font-size: 11px;
  color: #5f6675;
  transition: transform 0.15s ease;
}

.row-caret.open {
  transform: rotate(90deg);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 2px 10px 10px 10px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 9px;
  border-radius: 5px;
  background: #1a1f29;
  border: 1px solid #232833;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.chip em {
  font-style: normal;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.chip-note {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  align-self: center;
}

.add-session {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
  padding: 8px;
  border: 1px dashed #2a303c;
  border-radius: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12.5px;
  cursor: pointer;
}

.add-session:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.empty-batch {
  padding: 46px 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}
</style>
