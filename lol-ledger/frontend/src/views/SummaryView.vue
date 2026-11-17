<template>
  <div v-loading="loading && loaded" element-loading-text="正在刷新…" class="page summary-view">
    <div class="page-head">
      <div>
        <h1>操作人汇总</h1>
        <p class="muted small">
          {{ formatMoment(data.date_from) }} ~ {{ formatMoment(data.date_to) }} ·
          {{
            data.dividend_mode === 'fixed'
              ? `每局 ¥${formatCents(data.dividend_fixed_cents)} 分红`
              : `茶水分红 ${data.dividend_rate_percent}%`
          }}
        </p>
      </div>
      <div class="head-actions">
        <el-date-picker
          v-model="range"
          type="datetimerange"
          value-format="YYYY-MM-DDTHH:mm"
          format="MM-DD HH:mm"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          :clearable="false"
          :shortcuts="shortcuts"
          :style="{ width: '330px' }"
          @change="load"
        />
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="VideoPlay" @click="openSession">开一局</el-button>
      </div>
    </div>

    <div v-if="error" class="panel state-panel">
      <div class="state-title">数据暂不可用</div>
      <div class="state-desc muted">操作人汇总没有加载成功，请检查网络或服务后重试。</div>
      <el-button type="primary" :loading="loading" @click="load">重试</el-button>
    </div>
    <div
      v-else-if="!loaded"
      v-loading="true"
      element-loading-text="正在加载汇总数据…"
      class="panel state-panel state-loading"
    >
      <div class="state-title">正在加载汇总数据…</div>
    </div>
    <template v-else>
    <div class="totals">
      <div class="stat">
        <span>新增场次</span><b>{{ data.totals.session_count }}</b>
      </div>
      <div class="stat">
        <span>茶水合计</span><b>¥{{ formatCents(data.totals.tea_cents) }}</b>
      </div>
      <div class="stat">
        <span>收押金</span><b>¥{{ formatCents(data.totals.add_deposit_cents) }}</b>
      </div>
      <div class="stat">
        <span>退押金</span><b>¥{{ formatCents(data.totals.refund_cents) }}</b>
      </div>
      <div class="stat" :class="data.totals.cash_diff_cents < 0 ? 'warn' : 'good'">
        <span>现金差额</span><b>¥{{ formatCents(data.totals.cash_diff_cents) }}</b>
      </div>
      <div class="stat">
        <span>分红合计</span><b>¥{{ formatCents(data.totals.dividend_cents) }}</b>
      </div>
    </div>

    <div class="panel">
      <div class="section-head">
        <div class="section-title">按操作人</div>
        <span class="muted small">差额为正 = 店员应交，为负 = 店长应补</span>
      </div>

      <el-table v-if="data.rows.length" :data="data.rows" class="desktop-only" style="width: 100%">
        <el-table-column label="操作人" min-width="150">
          <template #default="{ row }">
            <div class="cell-main">{{ row.user?.display_name || '未知' }}</div>
            <div class="cell-sub">{{ row.user?.username || '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="场次" width="80" align="right">
          <template #default="{ row }"><b>{{ row.session_count }}</b></template>
        </el-table-column>
        <el-table-column label="人次" width="80" align="right">
          <template #default="{ row }">{{ row.player_times }}</template>
        </el-table-column>
        <el-table-column label="茶水" width="110" align="right">
          <template #default="{ row }">¥{{ formatCents(row.tea_cents) }}</template>
        </el-table-column>
        <el-table-column label="收押金" width="110" align="right">
          <template #default="{ row }">¥{{ formatCents(row.add_deposit_cents) }}</template>
        </el-table-column>
        <el-table-column label="退押金" width="110" align="right">
          <template #default="{ row }">¥{{ formatCents(row.refund_cents) }}</template>
        </el-table-column>
        <el-table-column label="差额" width="130" align="right">
          <template #default="{ row }">
            <span :class="row.cash_diff_cents < 0 ? 'diff-out' : 'diff-in'">
              ¥{{ formatCents(row.cash_diff_cents) }}
            </span>
            <div class="cell-sub">
              {{ row.cash_diff_cents < 0 ? '店长应补' : '店员应交' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="分红" width="110" align="right">
          <template #default="{ row }">
            <b class="div">¥{{ formatCents(row.dividend_cents) }}</b>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="data.rows.length" class="mobile-only summary-cards">
        <div v-for="row in data.rows" :key="row.user?.id || 'x'" class="summary-card">
          <div class="sc-head">
            <div class="cell-main">{{ row.user?.display_name || '未知' }}</div>
            <span :class="row.cash_diff_cents < 0 ? 'diff-out' : 'diff-in'">
              {{ row.cash_diff_cents < 0 ? '应补' : '应交' }}
              ¥{{ formatCents(Math.abs(row.cash_diff_cents)) }}
            </span>
          </div>
          <div class="sc-grid">
            <div><span>场次</span><b>{{ row.session_count }}</b></div>
            <div><span>茶水</span><b>¥{{ formatCents(row.tea_cents) }}</b></div>
            <div><span>收押金</span><b>¥{{ formatCents(row.add_deposit_cents) }}</b></div>
            <div><span>退押金</span><b>¥{{ formatCents(row.refund_cents) }}</b></div>
            <div><span>分红</span><b>¥{{ formatCents(row.dividend_cents) }}</b></div>
          </div>
        </div>
      </div>

      <el-empty v-if="!data.rows.length" description="这个区间没有记录" :image-size="88" />
    </div>

    <div class="panel">
      <div class="section-head">
        <div class="section-title">最近场次</div>
        <div class="spacer"></div>
        <el-button link type="primary" @click="router.push({ name: 'reports' })">查看全部</el-button>
      </div>
      <el-table v-if="sessions.length" :data="sessions" class="desktop-only" style="width: 100%">
        <el-table-column label="时间" width="150">
          <template #default="{ row }">
            <span class="muted">{{ formatShort(row.played_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="场次" min-width="160">
          <template #default="{ row }">
            <div class="cell-main">{{ row.name }}</div>
            <div class="cell-sub">{{ row.players.map((x: SessionPlayerRow) => x.game_id).join('、') }}</div>
          </template>
        </el-table-column>
        <el-table-column label="人次" width="80" align="right">
          <template #default="{ row }">{{ row.player_count }}</template>
        </el-table-column>
        <el-table-column label="茶水" width="110" align="right">
          <template #default="{ row }">¥{{ formatCents(row.tea_total_cents) }}</template>
        </el-table-column>
        <el-table-column label="操作人" width="110">
          <template #default="{ row }">
            <span class="muted">{{ row.operator?.display_name || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="sessions.length" class="mobile-only session-cards">
        <div v-for="row in sessions" :key="row.id" class="session-card">
          <div class="sc-head">
            <span class="cell-main">{{ row.name }}</span>
            <span class="mono">¥{{ formatCents(row.tea_total_cents) }}</span>
          </div>
          <div class="cell-sub">
            {{ row.players.map((x: SessionPlayerRow) => x.game_id).join('、') || '无玩家' }}
          </div>
          <div class="sc-meta">
            <span>{{ formatShort(row.played_at) }}</span>
            <span>{{ row.player_count }} 人次</span>
            <span>{{ row.operator?.display_name || '-' }}</span>
          </div>
        </div>
      </div>

      <el-empty v-if="!sessions.length" description="还没有场次" :image-size="80" />
    </div>
    </template>

    <NewSessionDialog
      v-model="sessionVisible"
      :default-tea-cents="defaultTeaCents"
      @created="onSessionCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { Refresh, VideoPlay } from '@element-plus/icons-vue'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { sessionApi, settingsApi, summaryApi } from '@/api'
import type { OperatorSummary, SessionPlayerRow, SessionRow } from '@/api/types'
import NewSessionDialog from '@/components/batches/NewSessionDialog.vue'
import {
  formatMoment,
  formatShort,
  momentShortcuts,
  todayMomentRange,
  todayText,
} from '@/utils/datetime'
import { formatCents } from '@/utils/money'

const router = useRouter()
const route = useRoute()

const shortcuts = momentShortcuts()
const day = todayText()
const range = ref<[string, string]>(todayMomentRange())
const data = ref<OperatorSummary>({
  date_from: day,
  date_to: day,
  dividend_mode: 'percent',
  dividend_rate_percent: 50,
  dividend_fixed_cents: 0,
  rows: [],
  totals: {
    session_count: 0,
    player_times: 0,
    tea_cents: 0,
    add_deposit_cents: 0,
    refund_cents: 0,
    cash_diff_cents: 0,
    dividend_cents: 0,
  },
})

const sessions = ref<SessionRow[]>([])
const defaultTeaCents = ref(200)
const sessionVisible = ref(false)
const loading = ref(false)
const error = ref(false)
const loaded = ref(false)
let loadSeq = 0

async function load() {
  const [from, to] = range.value || [day, day]
  const seq = ++loadSeq
  loading.value = true
  error.value = false
  try {
    const [summary, page] = await Promise.all([
      summaryApi.operators(from, to),
      sessionApi.list({ date_from: from, date_to: to, page: 1, page_size: 8 }),
    ])
    if (seq !== loadSeq) return
    data.value = summary
    sessions.value = page.items
    loaded.value = true
  } catch {
    if (seq !== loadSeq) return
    error.value = true
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

function openSession() {
  sessionVisible.value = true
}

async function onSessionCreated() {
  await load()
}

onMounted(async () => {
  try {
    const settings = await settingsApi.get()
    defaultTeaCents.value = settings.last_tea_cents
  } catch {
    // 设置读取失败不阻断汇总，茶水沿用本地默认值
  }
  await load()
  if (route.query.new) openSession()
})

// 顶部「开一局」在本页也会跳 ?new=1，这里保证弹窗一定打开
watch(
  () => route.query.new,
  (value) => {
    if (value) openSession()
  },
)
</script>

<style scoped>
.totals {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.totals .stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  background: var(--app-bg-panel);
}

.totals .stat span {
  font-size: 12px;
  color: var(--app-text-muted);
}

.totals .stat b {
  font-size: 19px;
  font-variant-numeric: tabular-nums;
}

.totals .stat.good b {
  color: var(--el-color-success);
}

.totals .stat.warn b {
  color: var(--el-color-warning);
}

.diff-in {
  color: var(--el-color-success);
  font-variant-numeric: tabular-nums;
}

.diff-out {
  color: var(--el-color-warning);
  font-variant-numeric: tabular-nums;
}

.div {
  color: var(--el-color-primary);
}

.summary-cards,
.session-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-card,
.session-card {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  background: var(--app-bg-panel);
}

.sc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 13px;
}

.sc-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.sc-grid > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sc-grid span {
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.sc-grid b {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.sc-meta {
  display: flex;
  gap: 10px;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

@media (max-width: 768px) {
  .totals {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .head-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .head-actions .el-date-editor {
    flex: 1 1 100%;
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
