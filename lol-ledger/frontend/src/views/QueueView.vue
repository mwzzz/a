<template>
  <div class="page queue-view">
    <div class="page-head">
      <div>
        <h1>排队登记</h1>
        <p class="muted small">
          {{ data.shop_name || '本店' }} · {{ data.date }} ·
          排队中 {{ counts.waiting }} 人，进行中 {{ counts.playing }} 人
        </p>
      </div>
      <div class="head-actions">
        <el-date-picker
          v-model="day"
          type="date"
          value-format="YYYY-MM-DD"
          :clearable="false"
          :style="{ width: '150px' }"
          @change="load"
        />
        <el-button :icon="Picture" :loading="rosterLoading" @click="openRoster">生成阵容图</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">登记排队</el-button>
      </div>
    </div>

    <div class="queue-stats">
      <div class="stat">
        <span>排队中</span><b>{{ counts.waiting }}</b>
      </div>
      <div class="stat">
        <span>上机中</span><b>{{ counts.playing }}</b>
      </div>
      <div class="stat">
        <span>今日完成</span><b>{{ counts.done }}</b>
      </div>
      <div class="stat">
        <span>已取消</span><b>{{ counts.cancelled }}</b>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h3>当前队列</h3>
        <span class="muted small">按登记先后排序，叫号后点「完成」</span>
      </div>

      <div v-loading="loading">
        <el-empty
          v-if="!active.length"
          description="还没有人排队，点右上角「登记排队」"
          :image-size="88"
        />

        <el-table v-else :data="active" class="desktop-only" style="width: 100%">
          <el-table-column label="#" width="56">
            <template #default="{ $index }">
              <span class="muted">{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="玩家" min-width="200">
            <template #default="{ row }">
              <div class="cell-main">{{ row.game_id }}</div>
              <div class="cell-sub">{{ row.note || '无备注' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="登记人" width="130">
            <template #default="{ row }">
              <span class="muted">{{ row.operator?.display_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="等待" width="100">
            <template #default="{ row }">
              <span class="mono">{{ row.wait_minutes }}</span> 分钟
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="tagType(row.status)" effect="light" size="small">
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'waiting'"
                link
                type="primary"
                @click="change(row, 'playing')"
              >
                叫号
              </el-button>
              <el-button
                v-else
                link
                type="success"
                @click="change(row, 'done')"
              >
                完成
              </el-button>
              <el-button link type="danger" @click="change(row, 'cancelled')">取消</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="active.length" class="mobile-only queue-cards">
          <div v-for="(row, index) in active" :key="row.id" class="queue-card">
            <div class="qc-head">
              <span class="qc-index">{{ index + 1 }}</span>
              <div class="qc-name">
                <div class="cell-main">{{ row.game_id }}</div>
                <div class="cell-sub">{{ row.note || '无备注' }}</div>
              </div>
              <el-tag :type="tagType(row.status)" effect="light" size="small">
                {{ row.status_label }}
              </el-tag>
            </div>
            <div class="qc-meta">
              <span>等待 {{ row.wait_minutes }} 分钟</span>
              <span>{{ row.operator?.display_name || '-' }} 登记</span>
            </div>
            <div class="qc-ops">
              <el-button
                v-if="row.status === 'waiting'"
                size="small"
                type="primary"
                plain
                @click="change(row, 'playing')"
              >
                叫号
              </el-button>
              <el-button v-else size="small" type="success" plain @click="change(row, 'done')">
                完成
              </el-button>
              <el-button size="small" type="danger" plain @click="change(row, 'cancelled')">
                取消
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="finished.length" class="panel">
      <div class="panel-head">
        <h3>已结束</h3>
        <span class="muted small">{{ finished.length }} 条</span>
      </div>
      <div class="finished-list">
        <div v-for="row in finished" :key="row.id" class="finished-item">
          <span class="fi-name">{{ row.game_id }}</span>
          <el-tag :type="tagType(row.status)" effect="plain" size="small">
            {{ row.status_label }}
          </el-tag>
          <span class="muted small">{{ shortTime(row.finished_at || row.created_at) }}</span>
        </div>
      </div>
    </div>

    <el-dialog v-model="createVisible" title="登记排队" width="420px" :close-on-click-modal="false">
      <el-form label-width="70px">
        <el-form-item label="游戏名" required>
          <el-input
            v-model="form.game_id"
            maxlength="64"
            placeholder="玩家游戏名"
            autocomplete="off"
            @keyup.enter="submitCreate"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" maxlength="100" placeholder="选填，例如：想坐 3 号机" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">登记</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rosterVisible" title="排队阵容图" width="430px">
      <div class="roster-wrap">
        <img v-if="rosterUrl" :src="rosterUrl" alt="排队阵容图" />
        <p class="muted small roster-tip">
          手机上长按图片保存到相册，再发到群里；电脑上点「下载图片」。
        </p>
      </div>
      <template #footer>
        <el-button @click="rosterVisible = false">关闭</el-button>
        <el-button type="primary" :icon="Download" @click="downloadRoster">下载图片</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Download, Picture, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { queueApi } from '@/api'
import type { QueueEntry, QueuePayload, QueueStatus } from '@/api/types'
import { buildRosterImage } from '@/utils/roster'

function localDay(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset()
  return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 10)
}

const day = ref(localDay())
const loading = ref(false)
const data = ref<QueuePayload>({
  date: day.value,
  shop_name: '',
  updated_at: '',
  entries: [],
  counts: { waiting: 0, playing: 0, done: 0, cancelled: 0 },
})

const active = computed(() =>
  data.value.entries.filter((item) => item.status === 'waiting' || item.status === 'playing'),
)
const finished = computed(() =>
  data.value.entries.filter((item) => item.status === 'done' || item.status === 'cancelled'),
)
const counts = computed(() => data.value.counts)

async function load() {
  loading.value = true
  try {
    data.value = await queueApi.list(day.value)
  } finally {
    loading.value = false
  }
}

function tagType(status: QueueStatus): 'warning' | 'success' | 'info' {
  if (status === 'waiting') return 'warning'
  if (status === 'playing') return 'success'
  return 'info'
}

function shortTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

const createVisible = ref(false)
const saving = ref(false)
const form = reactive({ game_id: '', note: '' })

function openCreate() {
  form.game_id = ''
  form.note = ''
  createVisible.value = true
}

async function submitCreate() {
  if (!form.game_id.trim()) {
    ElMessage.warning('请填游戏名')
    return
  }
  saving.value = true
  try {
    await queueApi.create({ game_id: form.game_id.trim(), note: form.note.trim() })
    createVisible.value = false
    ElMessage.success('已登记')
    await load()
  } finally {
    saving.value = false
  }
}

async function change(row: QueueEntry, status: QueueStatus) {
  if (status === 'cancelled') {
    try {
      await ElMessageBox.confirm(`确定取消「${row.game_id}」的排队？`, '取消排队', {
        type: 'warning',
        confirmButtonText: '确定取消',
        cancelButtonText: '再想想',
      })
    } catch {
      return
    }
  }
  await queueApi.setStatus(row.id, status)
  await load()
}

const rosterVisible = ref(false)
const rosterLoading = ref(false)
const rosterUrl = ref('')

async function openRoster() {
  rosterLoading.value = true
  try {
    const snapshot = await queueApi.snapshot(day.value)
    data.value = snapshot
    rosterUrl.value = buildRosterImage(snapshot)
    rosterVisible.value = true
  } finally {
    rosterLoading.value = false
  }
}

function downloadRoster() {
  if (!rosterUrl.value) return
  const link = document.createElement('a')
  link.href = rosterUrl.value
  link.download = `排队-${data.value.shop_name || '本店'}-${data.value.date}.png`
  link.click()
}

onMounted(load)
</script>

<style scoped>
.queue-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.queue-stats .stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  background: var(--app-bg-panel);
}

.queue-stats .stat span {
  font-size: 12px;
  color: var(--app-text-muted);
}

.queue-stats .stat b {
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}

.panel-head h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.queue-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.queue-card {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--app-border);
  background: var(--app-bg-panel);
}

.qc-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.qc-index {
  flex: none;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.12);
}

.qc-name {
  flex: 1;
  min-width: 0;
}

.qc-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.qc-ops {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.finished-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.finished-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--app-bg-subtle);
  font-size: 13px;
}

.fi-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.roster-wrap img {
  display: block;
  width: 100%;
  border-radius: 10px;
  border: 1px solid var(--app-border);
}

.roster-tip {
  margin: 10px 0 0;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .queue-stats {
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
</style>
