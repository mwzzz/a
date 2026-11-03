<template>
  <div class="page">
    <div class="page-head">
      <span class="page-title">平台管理</span>
      <span class="page-sub">开通商家 · 管理各店账号</span>
      <div class="spacer"></div>
      <el-button :icon="Refresh" @click="loadMerchants">刷新</el-button>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增商家</el-button>
    </div>

    <div class="stats">
      <div class="stat">
        <span>商家</span>
        <b>{{ merchants.length }}</b>
      </div>
      <div class="stat">
        <span>账号</span>
        <b>{{ totalUsers }}</b>
      </div>
      <div class="stat">
        <span>在册玩家</span>
        <b>{{ totalPlayers }}</b>
      </div>
    </div>

    <div class="panel">
      <el-table v-loading="loading" :data="merchants" empty-text="还没有商家，点右上角开通">
        <el-table-column label="商家" min-width="240">
          <template #default="{ row }">
            <div class="cell-main">{{ row.name }}</div>
            <div v-if="row.note" class="cell-sub">{{ row.note }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 'active' ? 'success' : 'info'"
              effect="plain"
            >
              {{ row.status === 'active' ? '营业中' : '已停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号" width="90" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.user_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="玩家" width="90" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.player_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="开通时间" width="150">
          <template #default="{ row }">
            <span class="muted">{{ formatShort(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="290" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openAccounts(row)">账号管理</el-button>
            <el-button link type="primary" @click="openEdit(row)">改名</el-button>
            <el-button
              link
              :type="row.status === 'active' ? 'danger' : 'success'"
              @click="toggleMerchant(row)"
            >
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="createVisible"
      title="开通商家"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="96px">
        <el-form-item label="商家名" required>
          <el-input v-model="createForm.name" maxlength="64" placeholder="例如 极光电竞" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.note" maxlength="200" placeholder="联系人、地址等（可空）" />
        </el-form-item>
        <el-divider content-position="left">第一个管理员</el-divider>
        <el-form-item label="同时创建">
          <el-switch v-model="createForm.withAdmin" />
        </el-form-item>
        <template v-if="createForm.withAdmin">
          <el-form-item label="用户名" required>
            <el-input v-model="createForm.admin_username" placeholder="例如 jg-boss" />
          </el-form-item>
          <el-form-item label="显示名">
            <el-input v-model="createForm.admin_display_name" maxlength="64" placeholder="例如 王店长" />
          </el-form-item>
          <el-form-item label="初始密码" required>
            <el-input
              v-model="createForm.admin_password"
              type="password"
              show-password
              autocomplete="off"
            />
          </el-form-item>
        </template>
      </el-form>
      <div class="hint">
        用户名全平台唯一，建议带门店前缀；密码至少 8 位，含字母和数字。开店后再关掉开关也行。
      </div>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">开通</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="修改商家" width="440px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="商家名" required>
          <el-input v-model="editForm.name" maxlength="64" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.note" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editing" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="drawerVisible"
      :title="current ? `账号管理 · ${current.name}` : '账号管理'"
      size="760px"
    >
      <div class="toolbar">
        <el-button type="primary" :icon="Plus" @click="openCreateAccount">新增账号</el-button>
        <el-button :icon="Refresh" @click="loadAccounts">刷新</el-button>
        <div class="spacer"></div>
        <span class="muted small">停用账号会立即踢下线；改密码需要重新登录</span>
      </div>

      <el-table v-loading="accountLoading" :data="accounts" empty-text="还没有账号">
        <el-table-column label="用户名" min-width="160">
          <template #default="{ row }">
            <div class="cell-main">{{ row.username }}</div>
            <div class="cell-sub">{{ row.display_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            <el-select
              :model-value="row.role"
              size="small"
              :disabled="busyId === row.id"
              @change="(value: 'admin' | 'staff') => changeRole(row, value)"
            >
              <el-option label="管理员" value="admin" />
              <el-option label="店员" value="staff" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :disabled="busyId === row.id"
              @change="(value: boolean) => toggleActive(row, value)"
            />
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="140">
          <template #default="{ row }">
            <span class="muted">{{ row.last_login_at ? formatShort(row.last_login_at) : '从未登录' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="renameAccount(row)">改显示名</el-button>
            <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog
      v-model="accountVisible"
      :title="current ? `新增账号 · ${current.name}` : '新增账号'"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="accountForm.username" placeholder="例如 jg-01" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="accountForm.display_name" maxlength="64" placeholder="例如 小美" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="accountForm.role">
            <el-radio value="staff">店员</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input
            v-model="accountForm.password"
            type="password"
            show-password
            autocomplete="off"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="accountVisible = false">取消</el-button>
        <el-button type="primary" :loading="accountSaving" @click="submitAccount">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="400px" :close-on-click-modal="false">
      <div class="reset-who">给 <b>{{ resetTarget?.username }}</b> 设置新密码</div>
      <el-input
        v-model="resetPassword"
        type="password"
        show-password
        placeholder="至少 8 位，含字母和数字"
      />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSaving" @click="submitReset">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { platformApi } from '@/api'
import type { AccountRow, PlatformMerchantRow } from '@/api/types'
import { formatShort } from '@/utils/datetime'

const merchants = ref<PlatformMerchantRow[]>([])
const loading = ref(false)

const totalUsers = computed(() => merchants.value.reduce((sum, row) => sum + row.user_count, 0))
const totalPlayers = computed(() =>
  merchants.value.reduce((sum, row) => sum + row.player_count, 0),
)

const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
  name: '',
  note: '',
  withAdmin: true,
  admin_username: '',
  admin_display_name: '',
  admin_password: '',
})

const editVisible = ref(false)
const editing = ref(false)
const editTarget = ref<PlatformMerchantRow | null>(null)
const editForm = reactive({ name: '', note: '' })

const drawerVisible = ref(false)
const current = ref<PlatformMerchantRow | null>(null)
const accounts = ref<AccountRow[]>([])
const accountLoading = ref(false)
const busyId = ref<number | null>(null)

const accountVisible = ref(false)
const accountSaving = ref(false)
const accountForm = reactive({ username: '', display_name: '', role: 'staff', password: '' })

const resetVisible = ref(false)
const resetSaving = ref(false)
const resetTarget = ref<AccountRow | null>(null)
const resetPassword = ref('')

async function loadMerchants() {
  loading.value = true
  try {
    merchants.value = await platformApi.merchants()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.name = ''
  createForm.note = ''
  createForm.withAdmin = true
  createForm.admin_username = ''
  createForm.admin_display_name = ''
  createForm.admin_password = ''
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请填商家名')
    return
  }
  if (createForm.withAdmin) {
    if (!createForm.admin_username.trim() || !createForm.admin_password) {
      ElMessage.warning('管理员用户名和初始密码都要填')
      return
    }
    if (createForm.admin_password.length < 8) {
      ElMessage.warning('初始密码至少 8 位')
      return
    }
  }
  creating.value = true
  try {
    await platformApi.createMerchant({
      name: createForm.name.trim(),
      note: createForm.note.trim(),
      admin_username: createForm.withAdmin ? createForm.admin_username.trim() : null,
      admin_password: createForm.withAdmin ? createForm.admin_password : null,
      admin_display_name: createForm.withAdmin ? createForm.admin_display_name.trim() : '',
    })
    ElMessage.success(`已开通「${createForm.name.trim()}」`)
    createVisible.value = false
    await loadMerchants()
  } finally {
    creating.value = false
  }
}

function openEdit(row: PlatformMerchantRow) {
  editTarget.value = row
  editForm.name = row.name
  editForm.note = row.note
  editVisible.value = true
}

async function submitEdit() {
  if (!editTarget.value) return
  if (!editForm.name.trim()) {
    ElMessage.warning('商家名不能为空')
    return
  }
  editing.value = true
  try {
    await platformApi.updateMerchant(editTarget.value.id, {
      name: editForm.name.trim(),
      note: editForm.note.trim(),
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await loadMerchants()
  } finally {
    editing.value = false
  }
}

async function toggleMerchant(row: PlatformMerchantRow) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  if (next === 'disabled') {
    try {
      await ElMessageBox.confirm(
        `停用「${row.name}」后，该店所有账号立即无法登录，数据会保留。`,
        '停用商家',
        { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  await platformApi.updateMerchant(row.id, { status: next })
  ElMessage.success(next === 'active' ? '已启用' : '已停用')
  await loadMerchants()
}

async function openAccounts(row: PlatformMerchantRow) {
  current.value = row
  drawerVisible.value = true
  await loadAccounts()
}

async function loadAccounts() {
  if (!current.value) return
  accountLoading.value = true
  try {
    accounts.value = await platformApi.users(current.value.id)
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

async function submitAccount() {
  if (!current.value) return
  if (!accountForm.username.trim() || !accountForm.password) {
    ElMessage.warning('用户名和密码都要填')
    return
  }
  if (accountForm.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  accountSaving.value = true
  try {
    await platformApi.createUser(current.value.id, {
      username: accountForm.username.trim(),
      display_name: accountForm.display_name.trim(),
      role: accountForm.role,
      password: accountForm.password,
    })
    ElMessage.success('账号已创建')
    accountVisible.value = false
    await Promise.all([loadAccounts(), loadMerchants()])
  } finally {
    accountSaving.value = false
  }
}

async function changeRole(row: AccountRow, role: 'admin' | 'staff') {
  if (role === row.role) return
  busyId.value = row.id
  try {
    await platformApi.updateUser(row.id, { role })
    ElMessage.success('角色已更新')
  } finally {
    busyId.value = null
    await loadAccounts()
  }
}

async function toggleActive(row: AccountRow, value: boolean) {
  busyId.value = row.id
  try {
    await platformApi.updateUser(row.id, { is_active: value })
    ElMessage.success(value ? '已启用' : '已停用')
  } finally {
    busyId.value = null
    await loadAccounts()
  }
}

async function renameAccount(row: AccountRow) {
  try {
    const { value } = await ElMessageBox.prompt('新的显示名（只影响界面展示）', `修改 ${row.username}`, {
      inputValue: row.display_name,
      inputValidator: (text: string) => (text.trim() ? true : '显示名不能为空'),
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    await platformApi.updateUser(row.id, { display_name: value.trim() })
    ElMessage.success('已保存')
    await loadAccounts()
  } catch {
    /* 取消 */
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
    await platformApi.resetPassword(resetTarget.value.id, resetPassword.value)
    ElMessage.success('密码已重置，对方需要重新登录')
    resetVisible.value = false
  } finally {
    resetSaving.value = false
  }
}

onMounted(loadMerchants)
</script>

<style scoped>
.stats {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 16px;
  min-width: 120px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  color: var(--el-text-color-secondary);
  font-size: 12.5px;
}

.stat b {
  color: var(--el-text-color-primary);
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.hint {
  padding: 10px 12px;
  background: #101319;
  border: 1px solid #1c2028;
  border-radius: 8px;
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
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
