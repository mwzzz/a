<template>
  <div class="zj-admin">
    <div class="toolbar">
      <el-button :icon="Refresh" @click="load">刷新</el-button>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增账号</el-button>
      <div class="spacer"></div>
      <span class="muted small">用户入口：/zj/login</span>
    </div>

    <div class="stats">
      <div class="stat">
        <span>账号</span>
        <b>{{ overview.users }}</b>
        <small>启用 {{ overview.active_users }}</small>
      </div>
      <div class="stat">
        <span>剩余次数合计</span>
        <b>{{ overview.remaining }}</b>
      </div>
      <div class="stat">
        <span>今日消耗</span>
        <b>{{ overview.today_used }}</b>
        <small>次</small>
      </div>
    </div>

    <el-table v-loading="loading" :data="users" empty-text="还没有查战绩账号，点上方新增">
      <el-table-column label="账号" min-width="180">
        <template #default="{ row }">
          <div class="cell-main">{{ row.username }}</div>
          <div class="cell-sub">
            {{ row.display_name }}<template v-if="row.note"> · {{ row.note }}</template>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="总次数" width="88" align="right">
        <template #default="{ row }">
          <span class="mono">{{ row.quota_total }}</span>
        </template>
      </el-table-column>

      <el-table-column label="已用" width="80" align="right">
        <template #default="{ row }">
          <span class="mono muted">{{ row.quota_used }}</span>
        </template>
      </el-table-column>

      <el-table-column label="剩余" width="170">
        <template #default="{ row }">
          <div class="remain">
            <div class="remain-bar">
              <i
                :style="{ width: `${usedPercent(row)}%`, background: remainColor(row) }"
              ></i>
            </div>
            <b class="mono" :style="{ color: remainColor(row) }">{{ row.quota_remaining }}</b>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="84">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_active ? 'success' : 'info'" effect="plain">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="最近登录" width="150">
        <template #default="{ row }">
          <span class="muted">
            {{ row.last_login_at ? formatShort(row.last_login_at) : '从未登录' }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="286" align="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openGrant(row)">加次数</el-button>
          <el-button link type="primary" @click="openLogs(row)">流水</el-button>
          <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
          <el-button
            link
            :type="row.is_active ? 'warning' : 'success'"
            @click="toggleActive(row)"
          >
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createVisible" title="新增查战绩账号" width="440px" :close-on-click-modal="false">
      <el-form label-width="84px">
        <el-form-item label="用户名" required>
          <el-input v-model="createForm.username" placeholder="3~32 位小写字母/数字，如 zj-01" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="createForm.display_name" maxlength="64" placeholder="如 阿伟" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="createForm.password" type="password" show-password autocomplete="off" />
        </el-form-item>
        <el-form-item label="初始次数">
          <el-input-number v-model="createForm.quota_total" :min="0" :max="100000" controls-position="right" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.note" maxlength="200" placeholder="联系方式、付费情况等" />
        </el-form-item>
      </el-form>
      <p class="hint">密码至少 8 位，含字母和数字；创建后把用户名和密码发给对方，并告知入口 /zj/login。</p>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSaving" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="grantVisible"
      :title="grantTarget ? `调整次数 · ${grantTarget.username}` : '调整次数'"
      width="420px"
      :close-on-click-modal="false"
    >
      <div class="grant-info">
        当前剩余 <b>{{ grantTarget?.quota_remaining ?? 0 }}</b> 次（总 {{ grantTarget?.quota_total ?? 0 }} /
        已用 {{ grantTarget?.quota_used ?? 0 }}）
      </div>
      <el-form label-width="72px">
        <el-form-item label="增减">
          <el-input-number v-model="grantDelta" :min="-100000" :max="100000" :step="10" controls-position="right" />
          <span class="hint-inline">正数加、负数减</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="grantNote" maxlength="200" placeholder="如 微信收款 50 元" />
        </el-form-item>
      </el-form>
      <div class="grant-preview" :class="{ bad: grantInvalid }">
        {{ grantInvalid ? '调整后总次数会低于已用次数' : `调整后剩余 ${grantPreview} 次` }}
      </div>
      <template #footer>
        <el-button @click="grantVisible = false">取消</el-button>
        <el-button type="primary" :disabled="grantInvalid" :loading="grantSaving" @click="submitGrant">
          确定
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="400px" :close-on-click-modal="false">
      <div class="grant-info">给 <b>{{ resetTarget?.username }}</b> 设置新密码</div>
      <el-input v-model="resetPassword" type="password" show-password placeholder="至少 8 位，含字母和数字" />
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSaving" @click="submitReset">确定</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="logsVisible"
      :title="logsTarget ? `用量流水 · ${logsTarget.username}` : '用量流水'"
      size="520px"
    >
      <div v-loading="logsLoading" class="logs">
        <div v-if="!logs.length && !logsLoading" class="logs-empty">还没有充值或查询记录</div>
        <div v-for="item in logs" :key="`${item.type}-${item.id}`" class="log-row">
          <i class="log-dot" :class="item.type"></i>
          <div class="log-main">
            <div class="log-title" v-if="item.type === 'grant'">
              调整配额
              <b :class="(item.delta ?? 0) >= 0 ? 'plus' : 'minus'">
                {{ (item.delta ?? 0) >= 0 ? '+' : '' }}{{ item.delta }}
              </b>
              次
            </div>
            <div class="log-title" v-else>
              查询 {{ item.nickname }}
              <el-tag size="small" :type="item.ok ? 'success' : 'danger'" effect="plain">
                {{ item.ok ? `${item.games} 场` : '失败' }}
              </el-tag>
            </div>
            <div class="log-sub">
              {{ formatShort(item.created_at) }}
              <template v-if="item.type === 'grant'">
                · 余额 {{ item.remaining }} 次
                <template v-if="item.operator"> · 操作人 {{ item.operator }}</template>
                <template v-if="item.note"> · {{ item.note }}</template>
              </template>
              <template v-else-if="item.err_code"> · 错误码 {{ item.err_code }}</template>
            </div>
          </div>
        </div>
        <div v-if="logsMore" class="logs-more">
          <el-button size="small" :loading="logsLoading" @click="loadLogs(false)">加载更多</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { zjAdminApi } from '@/api'
import type { ZjAdminUser, ZjLogItem, ZjOverview } from '@/api/types'
import { formatShort } from '@/utils/datetime'

const users = ref<ZjAdminUser[]>([])
const overview = ref<ZjOverview>({ users: 0, active_users: 0, remaining: 0, today_used: 0 })
const loading = ref(false)

const createVisible = ref(false)
const createSaving = ref(false)
const createForm = reactive({
  username: '',
  display_name: '',
  password: '',
  quota_total: 50,
  note: '',
})

const grantVisible = ref(false)
const grantSaving = ref(false)
const grantTarget = ref<ZjAdminUser | null>(null)
const grantDelta = ref(50)
const grantNote = ref('')

const resetVisible = ref(false)
const resetSaving = ref(false)
const resetTarget = ref<ZjAdminUser | null>(null)
const resetPassword = ref('')

const logsVisible = ref(false)
const logsLoading = ref(false)
const logsTarget = ref<ZjAdminUser | null>(null)
const logs = ref<ZjLogItem[]>([])
const logsMore = ref(false)

const grantPreview = computed(() =>
  Math.max((grantTarget.value?.quota_remaining ?? 0) + grantDelta.value, 0),
)
const grantInvalid = computed(() => {
  if (!grantTarget.value) return true
  const total = grantTarget.value.quota_total + grantDelta.value
  return total < grantTarget.value.quota_used || total > 100000
})

function usedPercent(row: ZjAdminUser): number {
  if (!row.quota_total) return 100
  return Math.min((row.quota_used / row.quota_total) * 100, 100)
}

function remainColor(row: ZjAdminUser): string {
  if (row.quota_remaining <= 0) return '#ff6b6b'
  if (row.quota_remaining <= 5) return '#f0b429'
  return '#3ecf8e'
}

async function load() {
  loading.value = true
  try {
    const data = await zjAdminApi.users()
    users.value = data.users
    overview.value = data.overview
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.username = ''
  createForm.display_name = ''
  createForm.password = ''
  createForm.quota_total = 50
  createForm.note = ''
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.username.trim() || !createForm.password) {
    ElMessage.warning('用户名和初始密码都要填')
    return
  }
  if (createForm.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  createSaving.value = true
  try {
    await zjAdminApi.create({
      username: createForm.username.trim(),
      display_name: createForm.display_name.trim(),
      password: createForm.password,
      quota_total: createForm.quota_total,
      note: createForm.note.trim(),
    })
    ElMessage.success('账号已创建')
    createVisible.value = false
    await load()
  } finally {
    createSaving.value = false
  }
}

function openGrant(row: ZjAdminUser) {
  grantTarget.value = row
  grantDelta.value = 50
  grantNote.value = ''
  grantVisible.value = true
}

async function submitGrant() {
  if (!grantTarget.value || grantInvalid.value) return
  grantSaving.value = true
  try {
    const result = await zjAdminApi.grant(grantTarget.value.id, grantDelta.value, grantNote.value.trim())
    ElMessage.success(
      `已${grantDelta.value >= 0 ? '加' : '减'} ${Math.abs(grantDelta.value)} 次，当前剩余 ${result.user.quota_remaining} 次`,
    )
    grantVisible.value = false
    await load()
  } finally {
    grantSaving.value = false
  }
}

function openReset(row: ZjAdminUser) {
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
    await zjAdminApi.resetPassword(resetTarget.value.id, resetPassword.value)
    ElMessage.success('密码已重置，对方需要重新登录')
    resetVisible.value = false
  } finally {
    resetSaving.value = false
  }
}

async function toggleActive(row: ZjAdminUser) {
  if (row.is_active) {
    try {
      await ElMessageBox.confirm(
        `停用「${row.username}」后，对方立即无法登录，剩余次数会保留。`,
        '停用账号',
        { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  await zjAdminApi.update(row.id, { is_active: !row.is_active })
  ElMessage.success(row.is_active ? '已停用' : '已启用')
  await load()
}

async function openLogs(row: ZjAdminUser) {
  logsTarget.value = row
  logs.value = []
  logsMore.value = false
  logsVisible.value = true
  await loadLogs(true)
}

async function loadLogs(reset: boolean) {
  if (!logsTarget.value) return
  logsLoading.value = true
  try {
    const offset = reset ? 0 : logs.value.length
    const data = await zjAdminApi.logs(logsTarget.value.id, 50, offset)
    logs.value = reset ? data.items : [...logs.value, ...data.items]
    logsMore.value = data.has_more
  } finally {
    logsLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.zj-admin {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stats {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stat {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 16px;
  min-width: 130px;
  background: var(--app-bg-subtle);
  border: 1px solid var(--app-border);
  border-radius: 10px;
  color: var(--app-text-muted);
  font-size: 12.5px;
}

.stat b {
  color: var(--el-text-color-primary);
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.stat small {
  font-size: 11.5px;
  color: var(--app-text-faint);
}

.cell-main {
  font-weight: 600;
  font-size: 13px;
  line-height: 1.4;
}

.cell-sub {
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.remain {
  display: flex;
  align-items: center;
  gap: 8px;
}

.remain-bar {
  flex: 1;
  height: 7px;
  border-radius: 999px;
  background: var(--app-bg-subtle);
  overflow: hidden;
}

.remain-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.small {
  font-size: 12px;
}

.hint {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--app-text-muted);
}

.hint-inline {
  margin-left: 8px;
  font-size: 11.5px;
  color: var(--app-text-faint);
}

.grant-info {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.grant-preview {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(62, 207, 142, 0.1);
  color: #3ecf8e;
  font-size: 12.5px;
}

.grant-preview.bad {
  background: rgba(255, 92, 92, 0.1);
  color: #ff8f8f;
}

.logs {
  display: flex;
  flex-direction: column;
}

.logs-empty {
  padding: 28px 0;
  text-align: center;
  font-size: 12.5px;
  color: var(--app-text-muted);
}

.log-row {
  display: flex;
  gap: 10px;
  padding: 10px 2px;
  border-bottom: 1px solid var(--app-border);
}

.log-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #4c8dff;
}

.log-dot.query {
  background: #3ecf8e;
}

.log-main {
  flex: 1;
  min-width: 0;
}

.log-title {
  font-size: 13px;
  line-height: 1.5;
}

.log-sub {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--app-text-muted);
  line-height: 1.6;
  word-break: break-all;
}

.plus {
  color: #3ecf8e;
}

.minus {
  color: #ff8f8f;
}

.logs-more {
  display: flex;
  justify-content: center;
  padding: 12px 0;
}

@media (max-width: 768px) {
  .stats {
    gap: 8px;
  }

  .stat {
    flex: 1 1 auto;
    min-width: 0;
    padding: 8px 12px;
  }
}
</style>
