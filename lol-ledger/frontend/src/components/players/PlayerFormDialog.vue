<template>
  <el-dialog
    :model-value="modelValue"
    :title="player ? '编辑玩家' : '新增玩家'"
    width="440px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <el-form label-width="76px">
      <el-form-item label="游戏名" required>
        <el-input v-model="form.game_id" placeholder="游戏 id 或召唤师名" maxlength="64" />
      </el-form-item>
      <el-form-item label="账号">
        <el-input v-model="form.account" placeholder="可选，登录账号" maxlength="64" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input
          v-model="form.remark"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
          placeholder="可选，比如常来的时间段"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref, watch } from 'vue'

import { playerApi } from '@/api'
import type { PlayerRow } from '@/api/types'

const props = defineProps<{
  modelValue: boolean
  player: PlayerRow | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved', value: PlayerRow): void
}>()

const form = reactive({ game_id: '', account: '', remark: '' })
const saving = ref(false)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    form.game_id = props.player?.game_id || ''
    form.account = props.player?.account || ''
    form.remark = props.player?.remark || ''
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  if (!form.game_id.trim()) {
    ElMessage.warning('请填写游戏名')
    return
  }
  saving.value = true
  try {
    const payload = {
      game_id: form.game_id.trim(),
      account: form.account.trim(),
      remark: form.remark.trim(),
    }
    const row = props.player
      ? await playerApi.update(props.player.id, payload)
      : await playerApi.create(payload)
    ElMessage.success(props.player ? '已保存' : '已新增')
    emit('saved', row)
    close()
  } finally {
    saving.value = false
  }
}
</script>
