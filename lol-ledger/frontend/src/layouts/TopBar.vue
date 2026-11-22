<template>
  <header class="topbar">
    <div class="brand" @click="router.push(auth.isSuperadmin ? '/platform' : '/')">
      <span class="brand-mark">L</span>
      <span class="brand-name">LOL 记录管理</span>
    </div>

    <span v-if="auth.isSuperadmin" class="dev-tag">开发者</span>
    <span v-else-if="auth.merchantName" class="merchant-tag">{{ auth.merchantName }}</span>

    <nav class="nav desktop-only">
      <router-link
        v-for="item in navs"
        :key="item.name"
        :to="{ name: item.name }"
        class="nav-item"
        active-class="active"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="spacer"></div>

    <el-input
      v-if="!auth.isSuperadmin"
      v-model="keyword"
      class="search desktop-only"
      placeholder="搜索玩家"
      clearable
      @keyup.enter="doSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>

    <el-button
      v-if="!auth.isSuperadmin"
      type="primary"
      :icon="VideoPlay"
      class="open-session"
      @click="openSession"
    >
      开一局
    </el-button>

    <el-dropdown trigger="click" @command="onUserCommand">
      <span class="user">
        <span class="dot"></span>
        <span class="user-name">{{ auth.displayName || '未登录' }}</span>
        <el-icon class="caret"><ArrowDown /></el-icon>
      </span>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="password">修改密码</el-dropdown-item>
          <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <el-tooltip content="更新日志" placement="bottom">
      <el-button text circle class="log-btn" aria-label="更新日志" @click="logVisible = true">
        <el-icon><Memo /></el-icon>
      </el-button>
    </el-tooltip>

    <el-tooltip :content="app.theme === 'dark' ? '切换到亮色' : '切换到暗色'" placement="bottom">
      <el-button text circle class="icon-btn" @click="app.toggleTheme()">
        <el-icon>
          <Sunny v-if="app.theme === 'dark'" />
          <Moon v-else />
        </el-icon>
      </el-button>
    </el-tooltip>
  </header>

  <el-drawer v-model="logVisible" title="更新日志" size="min(440px, 92vw)">
    <div class="changelog">
      <section v-for="entry in CHANGELOG" :key="entry.date" class="log-entry">
        <div class="log-head">
          <span class="log-date">{{ entry.date }}</span>
          <span v-if="entry.version" class="log-version">{{ entry.version }}</span>
        </div>
        <div v-for="group in entry.groups" :key="group.title" class="log-group">
          <div class="log-group-title">{{ group.title }}</div>
          <ul class="log-list">
            <li v-for="item in group.items" :key="item">{{ item }}</li>
          </ul>
        </div>
      </section>
    </div>
  </el-drawer>

  <el-dialog v-model="pwdVisible" title="修改密码" width="420px" :close-on-click-modal="false">
    <el-form label-width="86px">
      <el-form-item label="原密码">
        <el-input v-model="pwd.old" type="password" show-password autocomplete="off" />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="pwd.next" type="password" show-password autocomplete="off" />
      </el-form-item>
      <el-form-item label="再输一次">
        <el-input v-model="pwd.confirm" type="password" show-password autocomplete="off" />
      </el-form-item>
      <div class="pwd-hint">至少 8 位，包含字母和数字。改完需要重新登录。</div>
    </el-form>
    <template #footer>
      <el-button @click="pwdVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submitPassword">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import {
  ArrowDown,
  Calendar,
  DataBoard,
  MagicStick,
  Memo,
  Moon,
  Search,
  Setting,
  Sunny,
  TrendCharts,
  User,
  VideoPlay,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { authApi } from '@/api'
import { CHANGELOG } from '@/data/changelog'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const app = useAppStore()

const navs = computed(() =>
  auth.isSuperadmin
    ? [{ name: 'platform', label: '商家与账号', icon: Setting }]
    : [
        { name: 'overview', label: '工作台', icon: DataBoard },
        { name: 'summary', label: '汇总', icon: Calendar },
        { name: 'players', label: '玩家', icon: User },
        { name: 'reports', label: '报表', icon: TrendCharts },
        { name: 'settings', label: '设置', icon: Setting },
        { name: 'tools', label: '小工具', icon: MagicStick },
      ],
)

const keyword = ref('')
const pwdVisible = ref(false)
const logVisible = ref(false)
const saving = ref(false)
const pwd = reactive({ old: '', next: '', confirm: '' })

function doSearch() {
  const text = keyword.value.trim()
  router.push({ name: 'players', query: text ? { keyword: text } : {} })
}

function openSession() {
  app.openSessionDialog()
}

function onShortcut(event: KeyboardEvent) {
  if (event.key.toLowerCase() !== 'n' || event.metaKey || event.ctrlKey || event.altKey) return
  const target = event.target as HTMLElement | null
  if (target?.closest('input, textarea, select, [contenteditable="true"]')) return
  if (document.querySelector('.el-overlay')) return
  if (auth.isSuperadmin) return
  event.preventDefault()
  openSession()
}

async function onUserCommand(command: string) {
  if (command === 'password') {
    pwd.old = ''
    pwd.next = ''
    pwd.confirm = ''
    pwdVisible.value = true
    return
  }
  if (command === 'logout') {
    await auth.logout()
    router.replace({ name: 'login' })
  }
}

async function submitPassword() {
  if (pwd.next.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (pwd.next !== pwd.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  saving.value = true
  try {
    await authApi.changePassword(pwd.old, pwd.next)
    ElMessage.success('密码已修改，请重新登录')
    pwdVisible.value = false
    auth.reset()
    router.replace({ name: 'login' })
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onShortcut)
  if (!auth.isSuperadmin) void app.refreshToday()
})

onUnmounted(() => window.removeEventListener('keydown', onShortcut))

watch(
  () => route.fullPath,
  () => {
    if (!auth.isSuperadmin) void app.refreshToday()
  },
)
</script>

<style scoped>
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 22px;
  background: var(--app-bg-panel);
  border-bottom: 1px solid var(--app-border);
  position: sticky;
  top: 0;
  z-index: 20;
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  user-select: none;
  flex: none;
}

.brand-mark {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: var(--el-color-primary);
  color: #ffffff;
  font-weight: 700;
  display: grid;
  place-items: center;
  font-size: 15px;
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.merchant-tag,
.dev-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
  flex: none;
}

.merchant-tag {
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.3);
  color: var(--el-color-primary);
}

.dev-tag {
  background: var(--app-warning-soft);
  border: 1px solid rgba(230, 162, 60, 0.35);
  color: var(--el-color-warning);
}

.nav {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 6px;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 11px;
  border-radius: 7px;
  color: var(--app-text-muted);
  font-size: 13px;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-item:hover {
  color: var(--el-text-color-primary);
  background: var(--app-bg-hover);
}

.nav-item.active {
  color: var(--el-text-color-primary);
  background: var(--app-bg-subtle);
  font-weight: 600;
}

.search {
  width: 210px;
}

.open-session {
  flex: none;
}

.user {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 7px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-size: 13px;
  outline: none;
  flex: none;
}

.user:hover {
  background: var(--app-bg-hover);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-success);
  box-shadow: 0 0 0 3px var(--app-success-soft);
}

.pwd-hint {
  margin-left: 86px;
  font-size: 12px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.changelog {
  padding-bottom: 8px;
}

.log-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.log-date {
  font-size: 15px;
  font-weight: 600;
}

.log-version {
  padding: 1px 8px;
  border: 1px solid rgba(76, 141, 255, 0.35);
  border-radius: 999px;
  background: rgba(76, 141, 255, 0.1);
  font-size: 11px;
  color: var(--el-color-primary);
}

.log-group {
  margin-bottom: 14px;
}

.log-group-title {
  margin-bottom: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.log-list {
  margin: 0;
  padding-left: 18px;
  color: var(--el-text-color-regular);
  font-size: 12.5px;
  line-height: 1.85;
}

.log-list li {
  margin-bottom: 2px;
}

.log-list li::marker {
  color: var(--el-color-primary);
}

@media (max-width: 768px) {
  .topbar {
    height: 52px;
    padding: 0 12px;
    gap: 8px;
  }

  .brand-name {
    font-size: 14px;
  }

  .merchant-tag {
    max-width: 90px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: inline-block;
    line-height: 22px;
  }

  .user-name,
  .open-session .el-icon + span {
    display: none;
  }

  .open-session {
    padding: 8px;
  }

  .icon-btn {
    display: none;
  }
}
</style>
