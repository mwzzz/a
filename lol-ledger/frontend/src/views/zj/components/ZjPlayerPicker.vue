<template>
  <section class="picker">
    <div class="picker-head">
      <span class="picker-label">玩家列表</span>
      <span class="picker-hint">每行一个，可直接粘贴「昵称 #编号加入了队伍聊天」</span>
      <span class="spacer"></span>
      <span v-if="players.length" class="picker-count">{{ players.length }} 人</span>
    </div>

    <textarea
      class="picker-input"
      :value="text"
      :disabled="disabled"
      spellcheck="false"
      placeholder="有多少人和我一样#60733加入了队伍聊天&#10;兜兜是俺滴儿#45870加入了队伍聊天"
      @input="onInput"
    ></textarea>

    <div v-if="players.length" class="chips">
      <span v-for="player in players" :key="player.full" class="chip">
        <span class="chip-text">{{ player.full }}</span>
        <button
          v-if="!disabled"
          class="chip-x"
          type="button"
          :title="`移除 ${player.full}`"
          @click="emit('remove', player.full)"
        >
          ×
        </button>
      </span>
    </div>
    <p v-else-if="text.trim()" class="picker-empty">
      没解析到「昵称#编号」，检查一下粘贴内容里有没有 #数字。
    </p>
  </section>
</template>

<script setup lang="ts">
import type { ZjPlayer } from '@/utils/zjStats'

defineProps<{
  text: string
  players: ZjPlayer[]
  disabled: boolean
}>()

const emit = defineEmits<{
  (event: 'update:text', value: string): void
  (event: 'remove', full: string): void
}>()

function onInput(event: Event) {
  emit('update:text', (event.target as HTMLTextAreaElement).value)
}
</script>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.picker-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.picker-label {
  font-size: 13px;
  font-weight: 600;
}

.picker-hint {
  font-size: 12px;
  color: var(--app-text-muted);
}

.picker-count {
  font-size: 12px;
  color: #8db4ff;
  font-variant-numeric: tabular-nums;
}

.picker-input {
  width: 100%;
  min-height: 96px;
  max-height: 320px;
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-bg-subtle);
  color: var(--el-text-color-primary);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  resize: vertical;
  outline: none;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.picker-input:focus {
  border-color: #4c8dff;
  box-shadow: 0 0 0 3px rgba(76, 141, 255, 0.14);
}

.picker-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px 2px 10px;
  border: 1px solid rgba(76, 141, 255, 0.35);
  border-radius: 999px;
  background: rgba(76, 141, 255, 0.12);
  color: #9cc0ff;
  font-size: 12px;
}

.chip-x {
  width: 16px;
  height: 16px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #7f8798;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}

.chip-x:hover {
  background: rgba(255, 92, 92, 0.16);
  color: #ff8f8f;
}

.picker-empty {
  margin: 0;
  font-size: 12px;
  color: #ffb4b4;
}
</style>
