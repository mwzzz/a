<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">设置</span>
      <span class="page-sub">茶水默认值、押金提醒线、账号</span>
    </div>

    <el-tabs v-model="tab">
      <el-tab-pane label="基础设置" name="basic">
        <div class="panel form-panel">
          <el-form label-width="120px" style="max-width: 560px">
            <el-form-item label="店名">
              <el-input v-model="form.shop_name" maxlength="64" :disabled="!auth.isAdmin" />
            </el-form-item>
            <el-form-item label="默认茶水">
              <el-input v-model="form.last_tea" :disabled="!auth.isAdmin" autocomplete="off">
                <template #prefix>¥</template>
                <template #suffix>每人每局</template>
              </el-input>
            </el-form-item>
            <el-form-item label="押金不足线">
              <el-input v-model="form.low" :disabled="!auth.isAdmin" autocomplete="off">
                <template #prefix>¥</template>
                <template #suffix>低于这个数显示红色</template>
              </el-input>
            </el-form-item>
            <el-form-item label="押金充足线">
              <el-input v-model="form.high" :disabled="!auth.isAdmin" autocomplete="off">
                <template #prefix>¥</template>
                <template #suffix>高于这个数显示绿色</template>
              </el-input>
            </el-form-item>
            <el-form-item label="分红方式">
              <el-radio-group v-model="form.dividend_mode" :disabled="!auth.isAdmin">
                <el-radio-button value="percent">按茶水比例</el-radio-button>
                <el-radio-button value="fixed">每局固定</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="form.dividend_mode === 'percent'" label="分红比例">
              <el-input
                v-model="form.dividend_rate"
                :disabled="!auth.isAdmin"
                autocomplete="off"
              >
                <template #suffix>% · 按操作人茶水计算</template>
              </el-input>
            </el-form-item>
            <el-form-item v-else label="每局分红">
              <el-input
                v-model="form.dividend_fixed"
                :disabled="!auth.isAdmin"
                autocomplete="off"
              >
                <template #prefix>¥</template>
                <template #suffix>每局 · 按操作人局数计算</template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-button v-if="auth.isAdmin" type="primary" :loading="saving" @click="saveSettings">
                保存设置
              </el-button>
              <span v-else class="muted small">只有管理员可以修改设置</span>
            </el-form-item>
          </el-form>
          <div class="note">
            押金颜色规则：低于不足线红色，介于两者之间黄色，高于充足线绿色。开局扣茶水时如果余额不够会扣成负数。<br />
            分红方式：按茶水比例时，操作人分红 = 本人茶水 × 比例；每局固定时，操作人分红 = 本人局数 × 每局金额，与茶水多少无关。改动只影响之后关班的班次，已关班次的金额不变。
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="auth.isAdmin" label="账号管理" name="accounts">
        <div class="toolbar">
          <el-button type="primary" :icon="Plus" @click="openCreateAccount">新增账号</el-button>
          <el-button :icon="Refresh" @click="loadAccounts">刷新</el-button>
          <div class="spacer"></div>
          <span class="muted small">
            {{ auth.merchantName }} · 只能管理本店账号；店员可以记账，但不能删玩家、改设置、开账号
          </span>
        </div>

        <div class="panel desktop-only">
          <el-table v-loading="accountLoading" :data="accounts">
            <el-table-column label="用户名" min-width="150">
              <template #default="{ row }">
                <span class="cell-main">{{ row.username }}</span>
                <div v-if="row.id === auth.user?.id" class="cell-sub">这是你</div>
              </template>
            </el-table-column>
            <el-table-column label="显示名" width="140">
              <template #default="{ row }">
                <el-input
                  v-if="row.id === editingId"
                  v-model="editingName"
                  size="small"
                  @keyup.enter="saveName(row)"
                />
                <span v-else>{{ row.display_name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="角色" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.role === 'admin' ? 'warning' : 'info'" effect="plain">
                  {{ row.role === 'admin' ? '管理员' : '店员' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_active"
                  :disabled="row.id === auth.user?.id"
                  @change="(value: boolean) => toggleActive(row, value)"
                />
              </template>
            </el-table-column>
            <el-table-column label="最后登录" width="150">
              <template #default="{ row }">
                <span class="muted">{{ row.last_login_at ? formatShort(row.last_login_at) : '从未登录' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" align="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="startEditName(row)">改显示名</el-button>
                <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="mobile-only">
          <div v-loading="accountLoading" class="account-cards">
            <div v-for="row in accounts" :key="row.id" class="account-card">
              <div class="account-card-head">
                <div>
                  <div class="cell-main">{{ row.username }}</div>
                  <div v-if="row.id === auth.user?.id" class="cell-sub">这是你</div>
                </div>
                <el-tag size="small" :type="row.role === 'admin' ? 'warning' : 'info'" effect="plain">
                  {{ row.role === 'admin' ? '管理员' : '店员' }}
                </el-tag>
              </div>
              <div class="account-card-row">
                <span class="muted">显示名</span>
                <div class="account-card-value">
                  <el-input
                    v-if="row.id === editingId"
                    v-model="editingName"
                    size="small"
                    @keyup.enter="saveName(row)"
                  />
                  <span v-else>{{ row.display_name }}</span>
                  <el-button v-if="row.id === editingId" size="small" type="primary" @click="saveName(row)">
                    保存
                  </el-button>
                </div>
              </div>
              <div class="account-card-row">
                <span class="muted">状态</span>
                <el-switch
                  :model-value="row.is_active"
                  :disabled="row.id === auth.user?.id"
                  @change="(value: boolean) => toggleActive(row, value)"
                />
              </div>
              <div class="account-card-row">
                <span class="muted">最后登录</span>
                <span>{{ row.last_login_at ? formatShort(row.last_login_at) : '从未登录' }}</span>
              </div>
              <div class="account-card-ops">
                <el-button size="small" @click="startEditName(row)">改显示名</el-button>
                <el-button size="small" @click="openReset(row)">重置密码</el-button>
              </div>
            </div>
            <div v-if="!accountLoading && !accounts.length" class="empty-hint">还没有账号</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="auth.isAdmin" label="数据自检" name="check">
        <div class="panel check-panel">
          <div class="check-head">
            <div>
              <div class="check-title">数据自检</div>
              <div class="muted small">
                校验「玩家押金余额 = 流水合计 = 最后一条余额」。正常营业不用跑，只有手工改过数据库、恢复备份或怀疑数据异常时才需要。
              </div>
            </div>
            <div class="spacer"></div>
            <el-button type="primary" :loading="checking" @click="runCheck">
              立即自检
            </el-button>
          </div>

          <div v-if="report" class="check-report" :class="report.ok ? 'ok' : 'bad'">
            <div class="check-line">
              <el-icon><CircleCheck v-if="report.ok" /><Warning v-else /></el-icon>
              <span v-if="report.ok">
                数据一致，共检查 {{ report.checked }} 个玩家，押金合计 ¥{{ formatCents(report.total_deposit_cents) }}
              </span>
              <span v-else>
                发现 {{ report.problems.length }} 个异常，请立即检查
              </span>
            </div>
            <el-table v-if="!report.ok" :data="report.problems" size="small">
              <el-table-column prop="game_id" label="玩家" min-width="140" />
              <el-table-column label="记录的押金" width="130" align="right">
                <template #default="{ row }">¥{{ formatCents(row.stored_cents) }}</template>
              </el-table-column>
              <el-table-column label="流水合计" width="130" align="right">
                <template #default="{ row }">¥{{ formatCents(row.ledger_sum_cents) }}</template>
              </el-table-column>
              <el-table-column label="最后余额" width="130" align="right">
                <template #default="{ row }">¥{{ formatCents(row.last_balance_cents) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="accountVisible" title="新增账号" width="420px" :close-on-click-modal="false">
      <div class="reset-who">新账号会归属到 <b>{{ auth.merchantName }}</b></div>
      <el-form label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="accountForm.username" placeholder="3~32 位字母数字" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="accountForm.display_name" placeholder="比如 小美" maxlength="64" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="accountForm.role">
            <el-radio value="staff">店员</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="accountForm.password" type="password" show-password autocomplete="off" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="accountVisible = false">取消</el-button>
        <el-button type="primary" :loading="accountSaving" @click="createAccount">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="400px" :close-on-click-modal="false">
      <div class="reset-who">给 <b>{{ resetTarget?.username }}</b> 设置新密码</div>
      <el-input v-model="resetPassword" type="password" show-password placeholder="至少 8 位，含字母和数字" />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSaving" @click="submitReset">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { CircleCheck, Plus, Refresh, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref, watch } from 'vue'

import { accountApi, overviewApi, settingsApi } from '@/api'
import type { AccountRow, DividendMode, ReconcilePayload } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatShort } from '@/utils/datetime'
import { formatCents, parseYuan } from '@/utils/money'

const auth = useAuthStore()

const tab = ref('basic')
const form = reactive({
  shop_name: '',
  last_tea: '',
  low: '',
  high: '',
  dividend_mode: 'percent' as DividendMode,
  dividend_rate: '50',
  dividend_fixed: '0.00',
})
const saving = ref(false)

const accounts = ref<AccountRow[]>([])
const accountLoading = ref(false)
const accountVisible = ref(false)
const accountSaving = ref(false)
const accountForm = reactive({ username: '', display_name: '', role: 'staff', password: '' })

const editingId = ref<number | null>(null)
const editingName = ref('')

const resetVisible = ref(false)
const resetTarget = ref<AccountRow | null>(null)
const resetPassword = ref('')
const resetSaving = ref(false)

const checking = ref(false)
const report = ref<ReconcilePayload | null>(null)

async function loadSettings() {
  const data = await settingsApi.get()
  form.shop_name = data.shop_name
  form.last_tea = formatCents(data.last_tea_cents)
  form.low = formatCents(data.deposit_low_cents)
  form.high = formatCents(data.deposit_high_cents)
  form.dividend_mode = data.dividend_mode
  form.dividend_rate = String(data.dividend_rate_percent)
  form.dividend_fixed = formatCents(data.dividend_fixed_cents)
}

async function saveSettings() {
  const tea = parseYuan(form.last_tea)
  const low = parseYuan(form.low)
  const high = parseYuan(form.high)
  if (tea === null || low === null || high === null) {
    ElMessage.warning('金额格式不正确，最多两位小数')
    return
  }
  if (high <= low) {
    ElMessage.warning('押金充足线必须大于不足线')
    return
  }
  const rate = Number(form.dividend_rate)
  if (!Number.isInteger(rate) || rate < 0 || rate > 100) {
    ElMessage.warning('分红比例要填 0~100 的整数')
    return
  }
  const fixed = parseYuan(form.dividend_fixed)
  if (fixed === null) {
    ElMessage.warning('每局分红金额格式不正确，最多两位小数')
    return
  }
  if (form.dividend_mode === 'fixed' && fixed <= 0) {
    ElMessage.warning('按局分红时，每局金额要大于 0')
    return
  }
  saving.value = true
  try {
    await settingsApi.update({
      shop_name: form.shop_name.trim(),
      last_tea_cents: tea,
      deposit_low_cents: low,
      deposit_high_cents: high,
      dividend_rate_percent: rate,
      dividend_mode: form.dividend_mode,
      dividend_fixed_cents: fixed,
    })
    ElMessage.success('设置已保存')
    await loadSettings()
  } finally {
    saving.value = false
  }
}

async function runCheck() {
  checking.value = true
  try {
    report.value = await overviewApi.reconcile()
  } finally {
    checking.value = false
  }
}

async function loadAccounts() {
  if (!auth.isAdmin) return
  accountLoading.value = true
  try {
    accounts.value = await accountApi.list()
  } finally {
    accountLoading.value = false
  }
}

function openCreateAccount() {
  accountForm.username = ''
  accountForm.display_name = ''
  accountForm.role = 'staff'
  accountForm.password = ''
  accountVisible.value = true
}

async function createAccount() {
  if (!accountForm.username.trim() || !accountForm.password) {
    ElMessage.warning('用户名和密码都要填')
    return
  }
  accountSaving.value = true
  try {
    await accountApi.create({
      username: accountForm.username.trim(),
      display_name: accountForm.display_name.trim(),
      role: accountForm.role,
      password: accountForm.password,
    })
    ElMessage.success('账号已创建')
    accountVisible.value = false
    await loadAccounts()
  } finally {
    accountSaving.value = false
  }
}

function startEditName(row: AccountRow) {
  editingId.value = row.id
  editingName.value = row.display_name
}

async function saveName(row: AccountRow) {
  await accountApi.update(row.id, { display_name: editingName.value.trim() })
  editingId.value = null
  ElMessage.success('已保存')
  await loadAccounts()
}

async function toggleActive(row: AccountRow, value: boolean) {
  try {
    await accountApi.update(row.id, { is_active: value })
    ElMessage.success(value ? '已启用' : '已停用')
  } finally {
    await loadAccounts()
  }
}

function openReset(row: AccountRow) {
  resetTarget.value = row
  resetPassword.value = ''
  resetVisible.value = true
}

async function submitReset() {
  if (!resetTarget.value) return
  if (resetPassword.value.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  resetSaving.value = true
  try {
    await accountApi.resetPassword(resetTarget.value.id, resetPassword.value)
    ElMessage.success('密码已重置，对方需要重新登录')
    resetVisible.value = false
  } finally {
    resetSaving.value = false
  }
}

watch(tab, (value) => {
  if (value === 'accounts') loadAccounts()
})

onMounted(async () => {
  await loadSettings()
  if (auth.isAdmin) await loadAccounts()
})
</script>

<style scoped>
.form-panel {
  padding: 20px 20px 8px;
  max-width: 760px;
}

.note {
  margin-top: 6px;
  padding: 10px 12px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  border-radius: 8px;
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
  max-width: 640px;
}

.small {
  font-size: 12px;
}

.reset-who {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.check-panel {
  padding: 16px 18px;
}

.check-head {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.check-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.check-report {
  margin-top: 14px;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 12.5px;
}

.check-report.ok {
  background: rgba(62, 207, 142, 0.08);
  border: 1px solid rgba(62, 207, 142, 0.25);
  color: var(--el-color-success);
}

.check-report.bad {
  background: rgba(255, 92, 92, 0.08);
  border: 1px solid rgba(255, 92, 92, 0.3);
  color: var(--el-color-danger);
}

.check-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.check-report.bad .el-table {
  margin-top: 10px;
}

.account-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.account-card {
  padding: 12px 14px;
  background: var(--app-bg-panel);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.account-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--app-border);
}

.account-card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
  font-size: 12.5px;
}

.account-card-value {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.account-card-ops {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.account-card-ops :deep(.el-button) {
  flex: 1;
  margin-left: 0;
}

@media (max-width: 768px) {
  .form-panel {
    padding: 16px 14px 4px;
  }

  .form-panel :deep(.el-form-item) {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }

  .form-panel :deep(.el-form-item__label) {
    width: auto !important;
    justify-content: flex-start;
    padding: 0 0 4px;
    line-height: 1.4;
  }

  .form-panel :deep(.el-form-item__content) {
    margin-left: 0 !important;
  }

  .check-head {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
}
</style>
