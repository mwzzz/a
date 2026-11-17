<template>
  <el-select
    :model-value="modelValue ?? undefined"
    filterable
    remote
    clearable
    :remote-method="search"
    :loading="loading"
    :placeholder="placeholder"
    style="width: 100%"
    @update:model-value="onChange"
    @visible-change="onVisible"
  >
    <el-option
      v-for="item in options"
      :key="item.id"
      :value="item.id"
      :label="labelOf(item)"
      :disabled="isBlocked(item)"
    >
      <div class="option">
        <span>{{ item.game_id }}</span>
        <span class="sub">
          {{ item.account ? '段位 ' + item.account + ' · ' : '' }}
          <span :class="{ negative: item.balance_cents < 0 }">
            ¥{{ formatBalance(item.balance_cents, item.bonus_cents, item.deposit_cents) }}
          </span>
          <em v-if="item.is_blacklisted" class="tag danger">黑名单</em>
          <em v-else-if="isTeaFree(item)" class="tag">免茶水</em>
        </span>
      </div>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import { playerApi } from '@/api'
import type { PlayerOption } from '@/api/types'
import { formatBalance } from '@/utils/money'
import { nameKey } from '@/utils/names'

const props = withDefaults(
  defineProps<{
    modelValue?: number | null
    excludeIds?: number[]
    teaFreeKeys?: string[]
    placeholder?: string
  }>(),
  { modelValue: null, excludeIds: () => [], teaFreeKeys: () => [], placeholder: '搜索并选择玩家' },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: number | null): void
  (event: 'change', value: PlayerOption | null): void
}>()

const options = ref<PlayerOption[]>([])
const loading = ref(false)
let timer: number | undefined

function labelOf(item: PlayerOption): string {
  return `${item.game_id}${item.account ? ' · 段位 ' + item.account : ''} · 押金 ¥${formatBalance(item.balance_cents, item.bonus_cents, item.deposit_cents)}`
}

function isTeaFree(item: PlayerOption): boolean {
  return props.teaFreeKeys.includes(nameKey(item.game_id))
}

function isBlocked(item: PlayerOption): boolean {
  return item.is_blacklisted || isTeaFree(item)
}

async function load(keyword = '') {
  loading.value = true
  try {
    const data = await playerApi.options({
      keyword,
      exclude_ids: (props.excludeIds || []).join(','),
      limit: 20,
    })
    options.value = data
  } finally {
    loading.value = false
  }
}

function search(keyword: string) {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => load(keyword), 280)
}

function onVisible(visible: boolean) {
  if (visible) load('')
}

async function ensureSelected() {
  const id = props.modelValue
  if (!id) return
  if (options.value.some((item) => item.id === id)) return
  try {
    const player = await playerApi.get(id)
    options.value = [
      {
        id: player.id,
        game_id: player.game_id,
        account: player.account,
        is_blacklisted: player.is_blacklisted,
        deposit_cents: player.deposit_cents,
        bonus_cents: player.bonus_cents,
        balance_cents: player.balance_cents,
      },
      ...options.value,
    ]
  } catch {
    /* 玩家可能已被删除 */
  }
}

function onChange(value: number | null) {
  emit('update:modelValue', value ?? null)
  const found = options.value.find((item) => item.id === value) || null
  emit('change', found)
}

watch(() => props.modelValue, ensureSelected, { immediate: true })

defineExpose({ reload: load })
</script>

<style scoped>
.option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.sub {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tag {
  font-style: normal;
  font-size: 10.5px;
  line-height: 1;
  padding: 2px 5px;
  border-radius: 4px;
  border: 1px solid var(--app-border-strong);
  color: var(--el-text-color-secondary);
}

.tag.danger {
  color: var(--el-color-danger);
  border-color: var(--el-color-danger);
}

.negative {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
