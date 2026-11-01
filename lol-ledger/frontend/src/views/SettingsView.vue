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
            <el-form-item>
              <el-button v-if="auth.isAdmin" type="primary" :loading="saving" @click="saveSettings">
                保存设置
              </el-button>
              <span v-else class="muted small">只有管理员可以修改设置</span>
            </el-form-item>
          </el-form>
          <div class="note">
            押金颜色规则：低于不足线红色，介于两者之间黄色，高于充足线绿色。开局扣茶水时如果余额不够会扣成负数。
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

        <div class="panel">
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
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref, watch } from 'vue'

import { accountApi, settingsApi } from '@/api'
import type { AccountRow } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatShort } from '@/utils/datetime'
import { formatCents, parseYuan } from '@/utils/money'

const auth = useAuthStore()

const tab = ref('basic')
const form = reactive({ shop_name: '', last_tea: '', low: '', high: '' })
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

async function loadSettings() {
  const data = await settingsApi.get()
  form.shop_name = data.shop_name
  form.last_tea = formatCents(data.last_tea_cents)
  form.low = formatCents(data.deposit_low_cents)
  form.high = formatCents(data.deposit_high_cents)
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
  saving.value = true
  try {
    await settingsApi.update({
      shop_name: form.shop_name.trim(),
      last_tea_cents: tea,
      deposit_low_cents: low,
      deposit_high_cents: high,
    })
    ElMessage.success('设置已保存')
    await loadSettings()
  } finally {
    saving.value = false
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
  background: #101319;
  border: 1px solid #1c2028;
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
</style>
