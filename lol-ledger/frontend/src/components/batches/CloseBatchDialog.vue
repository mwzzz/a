<template>
  <el-dialog
    :model-value="modelValue"
    title="交班"
    width="560px"
    :close-on-click-modal="false"
    @update:model-value="close"
  >
    <div class="head">
      <span class="muted">即将结束</span>
      <b>{{ batch ? batch.label || formatBatchTime(batch) : '' }}</b>
      <span v-if="batch?.label" class="muted">{{ formatBatchTime(batch) }}</span>
    </div>

    <div v-loading="loading" class="stats">
      <div class="stat"><span>局数</span><b>{{ summary?.session_count ?? '-' }}</b></div>
      <div class="stat"><span>人次</span><b>{{ summary?.player_times ?? '-' }}</b></div>
      <div class="stat"><span>本班茶水</span><b>¥{{ formatCents(summary?.tea_total_cents ?? 0) }}</b></div>
      <div class="stat"><span>玩家押金余额</span><b>¥{{ formatCents(summary?.deposit_total_cents ?? 0) }}</b></div>
      <div class="stat"><span>本班收押金</span><b>¥{{ formatCents(summary?.add_total_cents ?? 0) }}</b></div>
      <div class="stat"><span>本班退押金</span><b>¥{{ formatCents(summary?.refund_total_cents ?? 0) }}</b></div>
    </div>

    <div class="custody">
      <div>
        <span class="muted">当前保管人</span>
        <b>{{ custody?.holder?.display_name || '未设置' }}</b>
      </div>
      <div>
        <span class="muted">在库现金</span>
        <b class="cash">¥{{ formatCents(custody?.amount_cents ?? 0) }}</b>
      </div>
    </div>

    <div v-if="!isHolder" class="warn">
      现金不在你手中，必须由当前保管人登录后交班。
    </div>
    <div v-if="depositCents < 0" class="warn">
      有玩家押金被茶水扣成负数，本次押金余额为负，建议先让对方补押金再交班。
    </div>

    <div class="split">
      <div class="split-title">交班后现金去向</div>

      <div class="split-row">
        <div class="split-left">
          <div class="split-name">茶水营业款</div>
          <div class="split-amount">¥{{ formatCents(teaCents) }}</div>
        </div>
        <div class="split-right">
          <el-select v-model="form.tea_to_user_id" placeholder="上缴给管理员" style="width: 100%">
            <el-option
              v-for="item in admins"
              :key="item.id"
              :label="`${item.display_name}（${item.username}）`"
              :value="item.id"
            />
          </el-select>
          <el-select v-model="form.tea_method" style="width: 100%">
            <el-option v-for="item in methods" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
      </div>

      <div class="split-row">
        <div class="split-left">
          <div class="split-name">玩家押金余额</div>
          <div class="split-amount">¥{{ formatCents(depositCents) }}</div>
        </div>
        <div class="split-right">
          <el-select v-model="form.deposit_to_user_id" placeholder="交给下一保管人" style="width: 100%">
            <el-option
              v-for="item in users"
              :key="item.id"
              :label="`${item.display_name}（${item.username}）`"
              :value="item.id"
            />
          </el-select>
          <el-select v-model="form.deposit_method" style="width: 100%">
            <el-option v-for="item in methods" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
      </div>
    </div>

    <div class="note">
      <label>交班备注</label>
      <el-input v-model="note" placeholder="可选，比如交给晚班" maxlength="200" />
    </div>

    <div class="tip">
      交班后这个批次不能再新增场次，汇总数字会保存成快照。茶水按管理员上缴，押金余额转给下一保管人。
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="loading || !isHolder"
        @click="submit"
      >
        确认交班
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

import { accountApi, batchApi } from '@/api'
import type { BatchRow, BatchSummary, CustodyInfo, HandoverMethod, UserOption } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatBatchTime } from '@/utils/batch'
import { formatCents } from '@/utils/money'

const props = defineProps<{
  modelValue: boolean
  batch: BatchRow | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'closed', value: BatchSummary): void
}>()

const auth = useAuthStore()
const summary = ref<BatchSummary | null>(null)
const custody = ref<CustodyInfo | null>(null)
const users = ref<UserOption[]>([])
const note = ref('')
const loading = ref(false)
const saving = ref(false)

const form = reactive({
  tea_to_user_id: 0,
  deposit_to_user_id: 0,
  tea_method: 'wechat' as HandoverMethod,
  deposit_method: 'wechat' as HandoverMethod,
})

const methods: { label: string; value: HandoverMethod }[] = [
  { label: '微信', value: 'wechat' },
  { label: '支付宝', value: 'alipay' },
  { label: '现金', value: 'cash' },
  { label: '银行转账', value: 'bank' },
  { label: '其他', value: 'other' },
]

const admins = computed(() => users.value.filter((item) => item.role === 'admin'))
const teaCents = computed(() => summary.value?.tea_total_cents ?? 0)
const depositCents = computed(() => summary.value?.deposit_total_cents ?? 0)
const isHolder = computed(
  () => Boolean(custody.value?.holder_id) && custody.value?.holder_id === auth.user?.id,
)

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible || !props.batch) return
    note.value = ''
    summary.value = null
    custody.value = null
    users.value = []
    loading.value = true
    try {
      const [detail, options] = await Promise.all([
        batchApi.get(props.batch.id),
        accountApi.options(),
      ])
      summary.value = detail.summary
      custody.value = detail.custody
      users.value = options
      form.tea_to_user_id =
        options.find((item) => item.id === detail.custody.holder_id && item.role === 'admin')?.id ||
        options.find((item) => item.role === 'admin')?.id ||
        0
      form.deposit_to_user_id =
        detail.custody.holder_id || options.find((item) => item.role === 'admin')?.id || 0
    } finally {
      loading.value = false
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  if (!props.batch) return
  if (!form.tea_to_user_id || !form.deposit_to_user_id) {
    ElMessage.warning('请选择茶水接收人和押金接收人')
    return
  }
  saving.value = true
  try {
    const result = await batchApi.close(props.batch.id, {
      tea_to_user_id: form.tea_to_user_id,
      deposit_to_user_id: form.deposit_to_user_id,
      tea_method: form.tea_method,
      deposit_method: form.deposit_method,
      note: note.value.trim(),
    })
    ElMessage.success(
      `已交班：茶水 ¥${formatCents(result.tea_total_cents)} 上缴，押金 ¥${formatCents(
        result.deposit_total_cents,
      )} 已移交`,
    )
    emit('closed', result)
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  font-size: 13px;
}

.stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}

.stat {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  background: #101319;
  border: 1px solid #1e222b;
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}

.stat b {
  color: var(--el-text-color-primary);
  font-size: 13.5px;
  font-variant-numeric: tabular-nums;
}

.custody {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 12px;
  background: #101319;
  border: 1px solid #232833;
  border-radius: 8px;
  font-size: 12.5px;
}

.custody b {
  margin-left: 8px;
  font-size: 14px;
}

.custody .cash {
  color: var(--el-color-success);
}

.warn {
  margin-bottom: 12px;
  padding: 9px 12px;
  border-radius: 8px;
  background: rgba(230, 162, 60, 0.12);
  border: 1px solid rgba(230, 162, 60, 0.35);
  color: #e6a23c;
  font-size: 12.5px;
}

.split {
  border: 1px solid #1e222b;
  border-radius: 9px;
  padding: 10px 12px 4px;
  margin-bottom: 12px;
}

.split-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.split-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  align-items: center;
  padding-bottom: 10px;
}

.split-name {
  font-size: 12.5px;
  color: var(--el-text-color-regular);
}

.split-amount {
  margin-top: 2px;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-color-success);
  font-variant-numeric: tabular-nums;
}

.split-right {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 8px;
}

.note {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.note label {
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
}

.tip {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
}
</style>
