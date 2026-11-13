<template>
  <div class="ai-wrap">
    <div v-if="!enabled" class="ai-disabled">
      <el-icon><MagicStick /></el-icon>
      <span>AI 识别未启用，请手动选择玩家</span>
    </div>

    <template v-else>
      <div
        class="drop"
        :class="{ dragging, busy: recognizing }"
        @click="pick"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <input
          ref="fileInput"
          class="file-input"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          @change="onInput"
        />

        <template v-if="!previewUrl">
          <el-icon class="drop-icon"><MagicStick /></el-icon>
          <div class="drop-title">AI 识别玩家</div>
          <div class="drop-hint">点击选择，或 Ctrl+V 粘贴 / 拖入截图</div>
          <div class="drop-hint tiny">jpg / png / webp / gif，最大 5MB</div>
        </template>

        <template v-else>
          <img :src="previewUrl" class="thumb" alt="截图预览" />
          <div class="file-meta">
            <div class="file-name">{{ fileName }}</div>
            <div v-if="recognizing" class="drop-hint">
              <el-icon class="is-loading"><Loading /></el-icon>
              识别中，约 3–8 秒
            </div>
            <div v-else-if="result" class="drop-hint">识别完成，确认后填入</div>
            <div v-else-if="errorText" class="drop-hint error-text">{{ errorText }}</div>
            <div v-else class="drop-hint">选择另一张图可重新识别</div>
          </div>
          <el-button v-if="recognizing" link type="info" @click.stop="cancel">
            取消
          </el-button>
          <el-button v-else link type="info" @click.stop="reset">移除</el-button>
        </template>
      </div>

      <div v-if="errorText && !recognizing && !result" class="error-box">
        {{ errorText }}
        <el-button link type="primary" @click="retry">重试</el-button>
      </div>

      <div v-if="result" class="result">
        <div class="result-head">
          <span>识别到 {{ result.count }} 人</span>
          <span class="tiny">耗时 {{ (result.elapsed_ms / 1000).toFixed(1) }}s</span>
        </div>
        <div v-for="item in rows" :key="item.raw_name" class="row" :class="item.status">
          <el-checkbox
            v-model="item.selected"
            :disabled="item.status === 'ambiguous' && !item.chooser"
          />
          <div class="raw">
            <span class="raw-name">{{ item.raw_name }}</span>
            <span v-if="item.team" class="team">队伍{{ item.team }}</span>
          </div>

          <div v-if="item.status === 'matched' && item.matched_player" class="target">
            {{ item.matched_player.game_id }}
          </div>
          <el-select
            v-else-if="item.status === 'ambiguous'"
            v-model="item.chooser"
            size="small"
            placeholder="选择匹配玩家"
            class="candidate"
            @change="item.selected = true"
          >
            <el-option
              v-for="candidate in item.candidates"
              :key="candidate.player.id"
              :label="`${candidate.player.game_id}（${Math.round(candidate.score * 100)}%）`"
              :value="candidate.player.id"
            />
          </el-select>
          <div v-else class="unmatched">
            未匹配
            <el-button
              link
              type="primary"
              :loading="creatingName === item.raw_name"
              @click="createPlayer(item)"
            >
              新建并选用
            </el-button>
          </div>
        </div>

        <div v-if="result.warnings.length" class="warn">
          {{ result.warnings.join('；') }}
        </div>

        <div class="actions">
          <el-button link @click="reset">重新识别</el-button>
          <div class="spacer"></div>
          <el-button type="primary" :disabled="!selectedIds.length" @click="apply">
            填入 {{ selectedIds.length }} 人
          </el-button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Loading, MagicStick } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { aiApi, playerApi } from '@/api'
import type { AiPlayerItem, AiRecognizePayload } from '@/api/types'

const props = defineProps<{
  active: boolean
}>()

const emit = defineEmits<{
  (event: 'apply', ids: number[]): void
}>()

interface RowState extends AiPlayerItem {
  selected: boolean
  chooser: number | null
}

const fileInput = ref<HTMLInputElement>()
const enabled = ref(false)
const recognizing = ref(false)
const dragging = ref(false)
const previewUrl = ref('')
const fileName = ref('')
const errorText = ref('')
const result = ref<AiRecognizePayload | null>(null)
const rows = ref<RowState[]>([])
const creatingName = ref<string | null>(null)
let currentFile: File | null = null
let controller: AbortController | null = null

const MAX_BYTES = 5 * 1024 * 1024
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

const selectedIds = computed(() => {
  const ids = rows.value
    .filter((item) => item.selected)
    .map((item) => {
      if (item.status === 'matched') return item.matched_player?.id
      if (item.status === 'ambiguous') return item.chooser
      return null
    })
    .filter((id): id is number => Boolean(id))
  return [...new Set(ids)].slice(0, 10)
})

onMounted(async () => {
  window.addEventListener('paste', onPaste)
  try {
    enabled.value = (await aiApi.status()).enabled
  } catch {
    enabled.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('paste', onPaste)
  controller?.abort()
  releasePreview()
})

watch(
  () => props.active,
  (active) => {
    if (!active) {
      controller?.abort()
      recognizing.value = false
      reset()
    }
  },
)

function releasePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}

function pick() {
  if (recognizing.value) return
  fileInput.value?.click()
}

function onInput(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) void recognize(file)
}

function onDrop(event: DragEvent) {
  dragging.value = false
  if (!enabled.value || recognizing.value) return
  const file = event.dataTransfer?.files?.[0]
  if (file) void recognize(file)
}

function onPaste(event: ClipboardEvent) {
  if (!props.active || !enabled.value || recognizing.value || result.value) return
  const file = Array.from(event.clipboardData?.files || []).find((item) =>
    item.type.startsWith('image/'),
  )
  if (!file) return
  event.preventDefault()
  void recognize(file)
}

function validate(file: File): boolean {
  if (!IMAGE_TYPES.includes(file.type) && !/\.(jpe?g|png|webp|gif)$/i.test(file.name)) {
    ElMessage.warning('请上传 jpg、png、webp 或 gif 图片')
    return false
  }
  if (file.size > MAX_BYTES) {
    ElMessage.warning('图片不能超过 5MB')
    return false
  }
  return true
}

async function recognize(file: File) {
  if (!validate(file)) return
  currentFile = file
  releasePreview()
  previewUrl.value = URL.createObjectURL(file)
  fileName.value = file.name
  errorText.value = ''
  result.value = null
  rows.value = []
  recognizing.value = true
  controller = new AbortController()

  try {
    const payload = await aiApi.recognize(file, controller.signal)
    result.value = payload
    rows.value = payload.items.map((item) => ({
      ...item,
      selected: item.status === 'matched',
      chooser: null,
    }))
  } catch (error: any) {
    if (error?.code === 'ERR_CANCELED') return
    errorText.value = error?.response?.data?.detail || '识别失败，请手动选人'
  } finally {
    recognizing.value = false
    controller = null
  }
}

function cancel() {
  controller?.abort()
  recognizing.value = false
}

function retry() {
  if (currentFile) void recognize(currentFile)
}

function reset() {
  controller?.abort()
  releasePreview()
  currentFile = null
  fileName.value = ''
  errorText.value = ''
  result.value = null
  rows.value = []
}

async function createPlayer(item: RowState) {
  let gameId = item.raw_name
  try {
    const result = await ElMessageBox.prompt(
      '确认识别到的玩家名，可以改完再创建',
      '新建玩家',
      {
        inputValue: item.raw_name,
        inputValidator: (value: string) => (value.trim() ? true : '玩家名不能为空'),
        confirmButtonText: '创建并选用',
        cancelButtonText: '取消',
      },
    )
    gameId = result.value.trim()
  } catch {
    return
  }

  creatingName.value = item.raw_name
  try {
    const created = await playerApi.create({ game_id: gameId })
    item.matched_player = {
      id: created.id,
      game_id: created.game_id,
      account: created.account || '',
      deposit_cents: created.deposit_cents,
    }
    item.status = 'matched'
    item.selected = true
    ElMessage.success(`已新建玩家 ${created.game_id}`)
  } finally {
    creatingName.value = null
  }
}

function apply() {
  if (!selectedIds.value.length) return
  emit('apply', selectedIds.value)
}
</script>

<style scoped>
.ai-wrap {
  margin-bottom: 16px;
}

.ai-disabled {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border: 1px dashed var(--app-border-strong);
  border-radius: 10px;
  color: var(--app-text-muted);
  font-size: 12.5px;
  background: var(--app-bg-subtle);
}

.drop {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 92px;
  padding: 12px 14px;
  border: 1px dashed var(--app-border-strong);
  border-radius: 10px;
  background: var(--app-bg-subtle);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.drop:hover,
.drop.dragging {
  border-color: var(--el-color-primary);
  background: var(--app-bg-hover);
}

.drop.busy {
  cursor: progress;
}

.file-input {
  display: none;
}

.drop-icon {
  font-size: 30px;
  color: var(--app-text-faint);
}

.drop-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 3px;
}

.drop-hint {
  font-size: 11.5px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.drop-hint.tiny,
.tiny {
  font-size: 11px;
  color: var(--app-text-faint);
}

.thumb {
  width: 108px;
  height: 62px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--app-border-strong);
  flex: none;
}

.file-meta {
  min-width: 0;
  flex: 1;
}

.file-name {
  font-size: 12.5px;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.error-text {
  color: var(--el-color-danger);
}

.error-box {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 7px;
  background: rgba(245, 108, 108, 0.08);
  border: 1px solid rgba(245, 108, 108, 0.3);
  font-size: 12px;
  color: var(--el-color-danger);
}

.result {
  margin-top: 10px;
  border: 1px solid var(--app-border);
  border-radius: 9px;
  background: var(--app-bg-page);
  overflow: hidden;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--app-border);
}

.row {
  display: grid;
  grid-template-columns: 22px minmax(120px, 1fr) minmax(150px, 1.3fr);
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-bottom: 1px solid var(--app-border);
  font-size: 12.5px;
  border-left: 2px solid transparent;
}

.row.matched {
  border-left-color: var(--el-color-success);
}

.row.ambiguous {
  border-left-color: var(--el-color-warning);
}

.row.unmatched {
  border-left-color: var(--el-color-danger);
}

.raw {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.raw-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team {
  flex: none;
  font-size: 10.5px;
  color: var(--app-text-muted);
  border: 1px solid var(--app-border-strong);
  border-radius: 4px;
  padding: 0 4px;
}

.target {
  color: var(--el-color-success);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.candidate {
  width: 100%;
}

.unmatched {
  color: var(--el-color-danger);
  display: flex;
  align-items: center;
  gap: 6px;
}

.warn {
  padding: 7px 12px;
  font-size: 11.5px;
  color: var(--el-color-warning);
  background: rgba(230, 162, 60, 0.06);
}

.actions {
  display: flex;
  align-items: center;
  padding: 8px 12px;
}

.spacer {
  flex: 1;
}
</style>
