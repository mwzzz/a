<template>
  <el-dialog
    :model-value="modelValue"
    title="批量导入玩家"
    width="540px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div class="rules">
      <div>仅支持 <b>.xls</b> / <b>.xlsx</b>，取第一个工作表。</div>
      <div>第一列：玩家 id（必填）；第二列：押金，单位元（可空）。</div>
      <div>第一行可以是表头；最多 1000 行；有一行错误整批都不会导入。</div>
    </div>

    <el-upload
      ref="uploadRef"
      v-model:file-list="fileList"
      drag
      :auto-upload="false"
      :limit="1"
      accept=".xls,.xlsx"
      :on-change="onChange"
      :on-remove="onRemove"
      :on-exceed="onExceed"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="el-upload__text">把 Excel 拖到这里，或 <em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">文件不能超过 5MB</div>
      </template>
    </el-upload>

    <div v-if="errorDetail" class="error-box">
      <div class="error-title">{{ errorDetail }}</div>
      <div v-if="errors.length" class="error-list">
        <div v-for="item in errors" :key="`${item.row}-${item.message}`">
          第 {{ item.row }} 行：{{ item.message }}
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="uploading"
        :disabled="!fileList.length || uploading"
        @click="submit"
      >
        开始导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import { ref, watch } from 'vue'

import { playerApi } from '@/api'
import type { PlayerImportError, PlayerImportResult } from '@/api/types'
import { formatCents } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved', value: PlayerImportResult): void
}>()

const uploadRef = ref<UploadInstance>()
const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const errorDetail = ref('')
const errors = ref<PlayerImportError[]>([])

const MAX_BYTES = 5 * 1024 * 1024

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    fileList.value = []
    errorDetail.value = ''
    errors.value = []
  },
)

function isExcel(name: string): boolean {
  return /\.(xls|xlsx)$/i.test(name)
}

function onChange(file: UploadFile) {
  errorDetail.value = ''
  errors.value = []
  const raw = file.raw
  if (!raw) return
  if (!isExcel(raw.name)) {
    ElMessage.warning('只支持 .xls 或 .xlsx 文件')
    fileList.value = []
    uploadRef.value?.clearFiles()
    return
  }
  if (raw.size > MAX_BYTES) {
    ElMessage.warning('文件不能超过 5MB')
    fileList.value = []
    uploadRef.value?.clearFiles()
  }
}

function onRemove() {
  errorDetail.value = ''
  errors.value = []
}

function onExceed() {
  ElMessage.warning('一次只能导入一个文件，请先移除已选文件')
}

function close() {
  if (uploading.value) return
  emit('update:modelValue', false)
}

async function submit() {
  const raw = fileList.value[0]?.raw
  if (!raw) {
    ElMessage.warning('请先选择 Excel 文件')
    return
  }
  uploading.value = true
  errorDetail.value = ''
  errors.value = []
  try {
    const result = await playerApi.importFile(raw)
    ElMessage.success(
      `已导入 ${result.created} 个玩家，押金合计 ¥${formatCents(result.deposited_cents)}`,
    )
    emit('saved', result)
    emit('update:modelValue', false)
  } catch (error: any) {
    const data = error?.response?.data
    if (typeof data?.detail === 'string') errorDetail.value = data.detail
    else errorDetail.value = '导入失败，请检查文件'
    if (Array.isArray(data?.errors)) {
      errors.value = data.errors as PlayerImportError[]
    }
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.rules {
  margin-bottom: 14px;
  padding: 10px 12px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
}

.rules b {
  color: var(--el-text-color-primary);
}

.upload-icon {
  font-size: 42px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.error-box {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 108, 108, 0.35);
  border-radius: 8px;
  background: rgba(245, 108, 108, 0.08);
  font-size: 12px;
  color: var(--el-color-danger);
}

.error-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.error-list {
  max-height: 160px;
  overflow: auto;
  line-height: 1.7;
}
</style>
