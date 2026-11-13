<template>
  <div class="zj-page">
    <section class="panel setup">
      <div class="settings">
        <label class="field area">
          <span>大区</span>
          <el-select v-model="areaId" :disabled="running" placeholder="选择大区">
            <el-option
              v-for="area in AREA_OPTIONS"
              :key="area.value"
              :label="area.label"
              :value="area.value"
            />
          </el-select>
        </label>

        <label class="field">
          <span>查询场次</span>
          <el-input-number
            v-model="allCount"
            :min="1"
            :max="100"
            :disabled="running"
            controls-position="right"
          />
        </label>

        <label class="field">
          <span>统计上限</span>
          <el-input-number
            v-model="capN"
            :min="10"
            :max="100"
            :disabled="running"
            controls-position="right"
          />
        </label>

        <span class="spacer"></span>
        <span class="cost-tip">一次最多 10 人，每次消耗 1 次额度</span>
      </div>

      <ZjPlayerPicker
        v-model:text="rawText"
        :players="players"
        :disabled="running"
        @remove="removePlayer"
      />

      <div class="actions">
        <el-button
          type="primary"
          size="large"
          :disabled="running || !players.length || auth.exhausted"
          :loading="starting"
          @click="start"
        >
          {{ starting ? '开批中…' : '开始查询' }}
        </el-button>
        <el-button v-if="running" type="danger" plain size="large" @click="stop">
          停止
        </el-button>
        <span v-if="auth.exhausted" class="limit warn">次数已用完，请联系管理员充值</span>
        <span v-else class="limit">剩余 {{ auth.remaining }} / {{ auth.total }} 次</span>
      </div>

      <el-progress
        v-if="running || progress > 0"
        class="progress"
        :percentage="Math.round(progress * 100)"
        :stroke-width="6"
        :show-text="false"
      />

      <div v-if="logs.length" ref="logBox" class="log">
        <div v-for="(line, index) in logs" :key="index" :class="line.cls">{{ line.text }}</div>
      </div>
    </section>

    <section class="panel result-panel">
      <div class="result-toolbar">
        <span class="toolbar-label">排序</span>
        <el-select v-model="sortKey" size="small" style="width: 168px">
          <el-option
            v-for="option in SORT_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <span class="spacer"></span>
        <span class="toolbar-hint">点击行首箭头展开对局明细</span>
      </div>

      <ZjResultPanel :rows="sortedRows" :failed="failedRows" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { zjApi, zjErrorMessage } from '@/api/zj'
import { useZjAuthStore } from '@/stores/zjAuth'
import {
  AREA_OPTIONS,
  loadChampionNames,
  parsePlayers,
  splitFull,
  statPlayer,
} from '@/utils/zjStats'

import ZjPlayerPicker from './components/ZjPlayerPicker.vue'
import ZjResultPanel from './components/ZjResultPanel.vue'
import { SORT_OPTIONS, type ZjResultRow, type ZjSortKey } from './types'

const SETTINGS_KEY = 'zj_settings'
const MAX_LOG_LINES = 200

const auth = useZjAuthStore()

const areaId = ref(1)
const allCount = ref(60)
const capN = ref(50)
const rawText = ref('')
const sortKey = ref<ZjSortKey>('winRate')

const running = ref(false)
const starting = ref(false)
const stopping = ref(false)
const progress = ref(0)
const logs = ref<{ text: string; cls: '' | 'ok' | 'err' }[]>([])
const results = ref<ZjResultRow[]>([])
const champNames = ref<Record<string, string>>({})
const logBox = ref<HTMLElement | null>(null)

const players = computed(() => parsePlayers(rawText.value))

const sortedRows = computed(() => {
  const rows = results.value.filter((row) => row.stat !== null)
  const key = sortKey.value
  return [...rows].sort((a, b) => {
    const left = a.stat!
    const right = b.stat!
    if (key === 'games') return right.games - left.games
    if (key === 'wins') return right.wins - left.wins
    if (key === 'kda') return (right.avgKDA?.rating ?? 0) - (left.avgKDA?.rating ?? 0)
    return right.winRate - left.winRate || right.games - left.games
  })
})

const failedRows = computed(() => results.value.filter((row) => row.stat === null))

onMounted(() => {
  loadSettings()
  loadChampionNames()
    .then((names) => {
      champNames.value = names
    })
    .catch(() => {
      /* 已在上层降级为「英雄{id}」 */
    })
})

watch([areaId, allCount, capN], saveSettings)

function loadSettings() {
  const raw = localStorage.getItem(SETTINGS_KEY)
  if (!raw) return
  try {
    const saved = JSON.parse(raw) as { area?: number; allCount?: number; capN?: number }
    if (saved.area) areaId.value = saved.area
    if (saved.allCount) allCount.value = saved.allCount
    if (saved.capN) capN.value = saved.capN
  } catch {
    /* 脏数据直接忽略 */
  }
}

function saveSettings() {
  localStorage.setItem(
    SETTINGS_KEY,
    JSON.stringify({ area: areaId.value, allCount: allCount.value, capN: capN.value }),
  )
}

function removePlayer(full: string) {
  rawText.value = players.value
    .filter((player) => player.full !== full)
    .map((player) => player.full)
    .join('\n')
}

function log(text: string, cls: '' | 'ok' | 'err' = '') {
  logs.value.push({ text, cls })
  if (logs.value.length > MAX_LOG_LINES) logs.value.splice(0, logs.value.length - MAX_LOG_LINES)
  void nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  })
}

function stop() {
  stopping.value = true
  log('停止中（当前这一个玩家查完就结束）…', 'err')
}

async function start() {
  if (running.value) return
  if (!players.value.length) {
    ElMessage.warning('先粘贴玩家列表（每行「昵称#编号」）')
    return
  }
  results.value = []
  logs.value = []
  progress.value = 0
  running.value = true
  starting.value = true
  stopping.value = false

  let batchId = 0
  let roster: string[] = []
  try {
    const batch = await zjApi.createBatch({
      area_id: areaId.value,
      all_count: allCount.value,
      players: players.value.map((player) => player.full),
    })
    batchId = batch.batch_id
    roster = batch.players
    auth.setQuota(batch.quota)
    log(`已扣 1 次，剩余 ${batch.quota.remaining} 次；本批 ${roster.length} 人`, 'ok')
  } catch (error) {
    const message = zjErrorMessage(error)
    running.value = false
    starting.value = false
    ElMessage.error(message)
    log(`✗ ${message}`, 'err')
    return
  } finally {
    starting.value = false
  }

  const total = roster.length

  for (let index = 0; index < total; index += 1) {
    if (stopping.value) break
    const full = roster[index]
    log(`[${index + 1}/${total}] 查询 ${full} …`)
    try {
      const response = await zjApi.queryPlayer(batchId, full)
      const stat = statPlayer(response.matches, capN.value, champNames.value)
      results.value.push({ player: splitFull(full), stat })
      log(
        `✓ ${full} 新模式 ${stat.games} 场，胜率 ${(stat.winRate * 100).toFixed(1)}%`,
        'ok',
      )
    } catch (error) {
      const message = zjErrorMessage(error)
      results.value.push({ player: splitFull(full), stat: null, error: message })
      log(`✗ ${full} ${message}`, 'err')
    }
    progress.value = (index + 1) / total
  }

  if (stopping.value) {
    await zjApi.closeBatch(batchId).catch(() => {
      /* 关批失败不影响本地状态 */
    })
    log(`已停止，共完成 ${results.value.length}/${total} 人（本次额度已消耗）`, 'err')
  } else {
    log(`完成，共 ${results.value.length} 名玩家`, 'ok')
  }

  running.value = false
  stopping.value = false
}
</script>

<style scoped>
.zj-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel {
  padding: 16px 18px;
}

.setup {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.field.area {
  min-width: 190px;
}

.field :deep(.el-input-number) {
  width: 118px;
}

.cost-tip {
  font-size: 11.5px;
  color: var(--app-text-faint);
  padding-bottom: 6px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.limit {
  font-size: 12px;
  color: var(--app-text-muted);
}

.limit.warn {
  color: #ffb4b4;
}

.progress {
  margin-top: 2px;
}

.log {
  max-height: 140px;
  overflow: auto;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  font-family: 'Consolas', 'Menlo', monospace;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--app-text-muted);
}

.log .ok {
  color: #3ecf8e;
}

.log .err {
  color: #ff8f8f;
}

.result-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-label {
  font-size: 12px;
  color: var(--app-text-muted);
}

.toolbar-hint {
  font-size: 11.5px;
  color: var(--app-text-faint);
}

@media (max-width: 768px) {
  .panel {
    padding: 12px 12px 14px;
  }

  .field.area {
    flex: 1 1 100%;
  }

  .settings {
    gap: 10px;
  }

  .field {
    flex: 1 1 40%;
  }

  .field :deep(.el-input-number) {
    width: 100%;
  }

  .toolbar-hint {
    display: none;
  }
}
</style>
