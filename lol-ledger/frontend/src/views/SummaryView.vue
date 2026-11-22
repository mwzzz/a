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
          value-format="YYYY-MM-DDTHH:mm:ss"
          format="MM-DD HH:mm:ss"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          :clearable="false"
          :shortcuts="shortcuts"
          :style="{ width: '330px' }"
          @change="load"
        />
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="VideoPlay" @click="app.openSessionDialog()">开一局</el-button>
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
        <div class="spacer"></div>
        <span class="muted small">差额为正 = 店员应交，为负 = 店长应补</span>
        <el-button v-if="auth.isAdmin" size="small" @click="continueFromLastPay">续接上次发薪</el-button>
        <el-button size="small" @click="generateReport">生成工资汇总</el-button>
        <el-button v-if="auth.isAdmin" size="small" type="primary" @click="payVisible = true">
          发工资
        </el-button>
      </div>

      <el-table
        v-if="displayRows.length"
        :data="displayRows"
        show-summary
        :summary-method="summaryMethod"
        class="desktop-only"
        style="width: 100%"
      >
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

      <div v-if="displayRows.length" class="mobile-only summary-cards">
        <div v-for="row in displayRows" :key="row.user?.id || 'x'" class="summary-card">
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

      <div v-if="displayRows.length" class="mobile-only summary-total">
        总计：场次 {{ data.totals.session_count }} ·
        茶水 ¥{{ formatCents(data.totals.tea_cents) }} ·
        收 ¥{{ formatCents(data.totals.add_deposit_cents) }} ·
        退 ¥{{ formatCents(data.totals.refund_cents) }} ·
        差额 ¥{{ formatCents(data.totals.cash_diff_cents) }} ·
        分红 ¥{{ formatCents(data.totals.dividend_cents) }}
      </div>

      <el-empty v-if="!displayRows.length" description="这个区间没有记录" :image-size="88" />

      <div v-if="reportVisible" class="report-box">
        <el-input v-model="reportText" type="textarea" :rows="reportRows" readonly resize="none" />
        <div class="report-actions">
          <el-button size="small" type="primary" @click="copyReport">复制</el-button>
          <el-button size="small" @click="reportVisible = false">收起</el-button>
        </div>
      </div>
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

    <SalaryPayDialog
      v-model="payVisible"
      :date-from="range[0]"
      :date-to="range[1]"
      @paid="load"
    />
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Refresh, VideoPlay } from '@element-plus/icons-vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { salaryApi, sessionApi, summaryApi } from '@/api'
import type {
  OperatorSummary,
  OperatorSummaryRow,
  SessionPlayerRow,
  SessionRow,
} from '@/api/types'
import SalaryPayDialog from '@/components/summary/SalaryPayDialog.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import {
  formatMoment,
  formatShort,
  momentShortcuts,
  recentMorningRange,
  todayText,
  withSeconds,
} from '@/utils/datetime'
import { formatCents, formatYuanShort } from '@/utils/money'

const router = useRouter()
const route = useRoute()
const app = useAppStore()
const auth = useAuthStore()

const MOMENT_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/

/** 区间来源优先级：URL ?from&to > 上次记忆(store) > 默认。分钟值补齐成秒级。 */
function initialRange(): [string, string] {
  const from = typeof route.query.from === 'string' ? route.query.from : ''
  const to = typeof route.query.to === 'string' ? route.query.to : ''
  if (MOMENT_RE.test(from) && MOMENT_RE.test(to)) return [withSeconds(from), withSeconds(to)]
  if (app.summaryRange) return [withSeconds(app.summaryRange[0]), withSeconds(app.summaryRange[1])]
  return recentMorningRange(1)
}

const shortcuts = momentShortcuts()
const day = todayText()
const range = ref<[string, string]>(initialRange())
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
const payVisible = ref(false)
const loading = ref(false)
const error = ref(false)
const loaded = ref(false)
let loadSeq = 0

async function load() {
  const [from, to] = range.value || [day, day]
  // 选定的区间持久化并同步到 URL，供切换页面/刷新/分享后恢复
  if (MOMENT_RE.test(from) && MOMENT_RE.test(to)) {
    app.setSummaryRange([from, to])
    if (route.query.from !== from || route.query.to !== to) {
      router.replace({ query: { ...route.query, from, to } })
    }
  }
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

async function continueFromLastPay() {
  try {
    const w = await salaryApi.nextWindow()
    range.value = [w.start, w.end]
    await load()
    ElMessage.success(
      w.source === 'last_paid'
        ? `已续接上次发薪：${w.start} ~ ${w.end}`
        : `暂无发薪记录，已用默认区间：${w.start} ~ ${w.end}`,
    )
  } catch {
    ElMessage.error('续接失败，请重试')
  }
}

// 列表展示层：隐藏「差额与分红都为 0」的人，并按场次倒序（不改动后端口径与合计）
const displayRows = computed<OperatorSummaryRow[]>(() =>
  data.value.rows
    .filter((row) => !(row.cash_diff_cents === 0 && row.dividend_cents === 0))
    .slice()
    .sort(
      (a, b) =>
        b.session_count - a.session_count ||
        b.cash_diff_cents - a.cash_diff_cents ||
        (a.user?.id ?? 0) - (b.user?.id ?? 0),
    ),
)

// 底部「总计」取后端 data.totals（全部行），保证被隐藏的人绝不影响合计
function summaryMethod({ columns }: { columns: unknown[] }): string[] {
  const t = data.value.totals
  return columns.map((_column, index) => {
    switch (index) {
      case 0:
        return '总计'
      case 1:
        return String(t.session_count)
      case 2:
        return String(t.player_times)
      case 3:
        return `¥${formatCents(t.tea_cents)}`
      case 4:
        return `¥${formatCents(t.add_deposit_cents)}`
      case 5:
        return `¥${formatCents(t.refund_cents)}`
      case 6:
        return `¥${formatCents(t.cash_diff_cents)}`
      case 7:
        return `¥${formatCents(t.dividend_cents)}`
      default:
        return ''
    }
  })
}

const reportVisible = ref(false)
const reportText = ref('')
const reportRows = computed(() =>
  Math.min(24, Math.max(6, reportText.value.split('\n').length)),
)

function momentDate(text: string): string {
  return `${Number(text.slice(5, 7))}月${Number(text.slice(8, 10))}日`
}

function momentLabel(text: string): string {
  const date = momentDate(text)
  const hhmm = text.slice(11, 16)
  if (!hhmm) return date
  const ss = text.slice(17, 19)
  return `${date}${hhmm}${ss && ss !== '00' ? `:${ss}` : ''}`
}

// 东亚宽字符（含全角空格 　）按 2 列，其余按 1 列，用于把各列对齐
function displayWidth(text: string): number {
  let width = 0
  for (const ch of text) {
    const code = ch.codePointAt(0) || 0
    const wide =
      (code >= 0x1100 && code <= 0x115f) ||
      (code >= 0x2e80 && code <= 0x303e) ||
      (code >= 0x3041 && code <= 0x33ff) ||
      (code >= 0x3400 && code <= 0x4dbf) ||
      (code >= 0x4e00 && code <= 0x9fff) ||
      (code >= 0xac00 && code <= 0xd7a3) ||
      (code >= 0xf900 && code <= 0xfaff) ||
      (code >= 0xfe30 && code <= 0xfe6f) ||
      (code >= 0xff00 && code <= 0xff60) ||
      (code >= 0xffe0 && code <= 0xffe6)
    width += wide ? 2 : 1
  }
  return width
}

function padWidth(text: string, target: number): string {
  let out = text
  let width = displayWidth(text)
  while (width < target) {
    if (target - width >= 2) {
      out += '　'
      width += 2
    } else {
      out += ' '
      width += 1
    }
  }
  return out
}

function generateReport() {
  const [from, to] = range.value || [day, day]
  const rows = displayRows.value
  const names = rows.map((row) => row.user?.display_name || row.user?.username || '未知')
  const wages = rows.map((row) => formatYuanShort(row.dividend_cents))
  const nameWidth = Math.max(0, ...names.map(displayWidth))
  const wageWidth = Math.max(0, ...wages.map(displayWidth))

  const lines = rows.map((row, index) => {
    const diff =
      row.cash_diff_cents > 0
        ? `应交${formatYuanShort(row.cash_diff_cents)}`
        : row.cash_diff_cents < 0
          ? `应补${formatYuanShort(-row.cash_diff_cents)}***`
          : ''
    const body = `${padWidth(names[index], nameWidth)}　工资${padWidth(wages[index], wageWidth)}`
    return diff ? `${body}　${diff}` : body
  })

  const head = `【${momentDate(from)}工资与差额明细】`
  const period = `统计时段：${momentLabel(from)} 至 ${momentLabel(to)}`
  const tail = `总计工资支出：${formatYuanShort(data.value.totals.dividend_cents)}元`
  reportText.value = [head, period, ...lines, tail].join('\n')
  reportVisible.value = true
  // 生成即自动复制，省去再点一次「复制」
  void copyReport()
}

async function copyReport() {
  const text = reportText.value
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
    return
  } catch {
    // http/非安全上下文下 navigator.clipboard 不可用，回退到 execCommand
  }
  const el = document.createElement('textarea')
  el.value = text
  el.style.position = 'fixed'
  el.style.opacity = '0'
  document.body.appendChild(el)
  el.select()
  try {
    document.execCommand('copy')
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选中文本复制')
  }
  document.body.removeChild(el)
}

onMounted(async () => {
  await load()
})

// 全局「开一局」弹窗创建场次后，本页刷新（不靠跳转，玩家页也能原地开局）
watch(
  () => app.sessionTick,
  () => void load(),
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

.summary-total {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  background: var(--app-bg-panel);
  font-size: 13px;
  color: var(--app-text-muted);
  line-height: 1.7;
}

.report-box {
  margin-top: 12px;
}

.report-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
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
