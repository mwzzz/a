<template>
  <div class="zj-shell">
    <header class="zj-top">
      <RouterLink class="zj-brand" to="/zj">
        <span class="zj-mark">Z</span>
        <span class="zj-brand-text">
          <b>新模式战队战绩</b>
          <small>粘贴队伍玩家 → 逐个查询 → 统计新模式</small>
        </span>
      </RouterLink>

      <div class="spacer"></div>

      <div
        class="quota-pill"
        :class="{ warn: auth.remaining <= 5, empty: auth.remaining <= 0 }"
        title="剩余次数 / 总次数"
      >
        <span class="quota-label">剩余</span>
        <b class="quota-num">{{ auth.remaining }}</b>
        <span class="quota-total">/ {{ auth.total }} 次</span>
      </div>

      <el-dropdown trigger="click" @command="onCommand">
        <button class="user-btn" type="button">
          {{ auth.displayName || '账号' }}
          <el-icon><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="password">修改密码</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <main class="zj-main">
      <router-view />
    </main>

    <el-dialog
      v-model="pwdVisible"
      title="修改密码"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form label-width="72px" @submit.prevent>
        <el-form-item label="原密码">
          <el-input
            v-model="oldPassword"
            type="password"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="newPassword"
            type="password"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
      </el-form>
      <p class="pwd-hint">至少 8 位，含字母和数字；改完需要重新登录。</p>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitPassword">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { zjApi, zjErrorMessage } from '@/api/zj'
import { useZjAuthStore } from '@/stores/zjAuth'

const router = useRouter()
const auth = useZjAuthStore()

const pwdVisible = ref(false)
const oldPassword = ref('')
const newPassword = ref('')
const saving = ref(false)

onMounted(() => {
  // 管理端可能刚加过次数，进来先拉一次余额
  auth.fetchMe().catch(() => {
    /* 401 由拦截器统一跳登录 */
  })
})

function onCommand(command: string) {
  if (command === 'password') {
    oldPassword.value = ''
    newPassword.value = ''
    pwdVisible.value = true
    return
  }
  if (command === 'logout') {
    auth.clear()
    void router.replace({ name: 'zj-login' })
  }
}

async function submitPassword() {
  if (!oldPassword.value || !newPassword.value) {
    ElMessage.warning('原密码和新密码都要填')
    return
  }
  if (newPassword.value.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  saving.value = true
  try {
    await zjApi.changePassword(oldPassword.value, newPassword.value)
    ElMessage.success('密码已修改，请重新登录')
    pwdVisible.value = false
    auth.clear()
    void router.replace({ name: 'zj-login' })
  } catch (error) {
    ElMessage.error(zjErrorMessage(error))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.zj-shell {
  min-height: 100%;
  background:
    radial-gradient(900px 420px at 50% -12%, rgba(64, 158, 255, 0.14), transparent 62%),
    var(--app-bg-page);
}

.zj-top {
  position: fixed;
  inset: 0 0 auto;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  height: 60px;
  padding: 0 20px;
  background: color-mix(in srgb, var(--app-bg-panel) 88%, transparent);
  border-bottom: 1px solid var(--app-border);
  backdrop-filter: blur(12px);
}

.zj-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.zj-mark {
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: linear-gradient(135deg, #4c8dff, #2f6bff);
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  box-shadow: 0 6px 18px rgba(47, 107, 255, 0.35);
}

.zj-brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
}

.zj-brand-text b {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.zj-brand-text small {
  color: var(--app-text-muted);
  font-size: 11.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quota-pill {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgba(76, 141, 255, 0.35);
  background: rgba(76, 141, 255, 0.12);
  color: #8db4ff;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.quota-pill b {
  font-size: 17px;
  color: #cfe0ff;
}

.quota-pill.warn {
  border-color: rgba(230, 162, 60, 0.45);
  background: rgba(230, 162, 60, 0.12);
  color: #f0b429;
}

.quota-pill.warn b {
  color: #ffd479;
}

.quota-pill.empty {
  border-color: rgba(255, 92, 92, 0.45);
  background: rgba(255, 92, 92, 0.12);
  color: #ff8f8f;
}

.quota-pill.empty b {
  color: #ffb4b4;
}

.quota-label {
  color: inherit;
  opacity: 0.75;
}

.user-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-bg-subtle);
  color: var(--el-text-color-regular);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease;
}

.user-btn:hover {
  border-color: var(--app-border-strong);
  background: var(--app-bg-hover);
}

.zj-main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 76px 20px 48px;
}

.pwd-hint {
  margin: 0;
  font-size: 12px;
  color: var(--app-text-muted);
}

@media (max-width: 768px) {
  .zj-top {
    height: 56px;
    padding: 0 12px;
    gap: 8px;
  }

  .zj-brand-text small {
    display: none;
  }

  .quota-total {
    display: none;
  }

  .zj-main {
    padding: 68px 12px 40px;
  }
}
</style>
