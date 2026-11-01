<template>
  <header class="topbar">
    <div class="brand" @click="router.push('/')">
      <span class="brand-mark">L</span>
      <span class="brand-name">LOL 记录管理</span>
    </div>

    <span v-if="auth.merchantName" class="merchant-tag">{{ auth.merchantName }}</span>

    <nav class="nav">
      <router-link
        v-for="item in navs"
        :key="item.name"
        :to="{ name: item.name }"
        class="nav-item"
        active-class="active"
      >
        {{ item.label }}
      </router-link>
    </nav>

    <div class="spacer"></div>

    <el-input
      v-model="keyword"
      class="search"
      placeholder="搜索玩家或场次"
      clearable
      @keyup.enter="doSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>

    <el-dropdown trigger="click" @command="onUserCommand">
      <span class="user">
        <span class="dot"></span>
        {{ auth.displayName || '未登录' }}
        <el-icon class="caret"><ArrowDown /></el-icon>
      </span>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="password">修改密码</el-dropdown-item>
          <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <el-tooltip :content="app.theme === 'dark' ? '切换到亮色' : '切换到暗色'" placement="bottom">
      <el-button text circle class="icon-btn" @click="app.toggleTheme()">
        <el-icon>
          <Sunny v-if="app.theme === 'dark'" />
          <Moon v-else />
        </el-icon>
      </el-button>
    </el-tooltip>

    <el-dropdown trigger="click" @command="onCreate">
      <el-button type="primary" :icon="Plus">新增</el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="session">新增场次</el-dropdown-item>
          <el-dropdown-item command="player">新增玩家</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </header>

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
import { ArrowDown, Moon, Plus, Search, Sunny } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { authApi } from '@/api'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const navs = [
  { name: 'overview', label: '总览' },
  { name: 'batches', label: '场次' },
  { name: 'players', label: '玩家' },
  { name: 'records', label: '记录' },
  { name: 'ledger', label: '账本' },
  { name: 'settings', label: '设置' },
]

const keyword = ref('')
const pwdVisible = ref(false)
const saving = ref(false)
const pwd = reactive({ old: '', next: '', confirm: '' })

function doSearch() {
  router.push({ name: 'records', query: keyword.value ? { keyword: keyword.value } : {} })
}

function onCreate(command: string) {
  if (command === 'session') {
    router.push({ name: 'batches', query: { new: '1' } })
  } else {
    router.push({ name: 'players', query: { new: '1' } })
  }
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
</script>

<style scoped>
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 22px;
  background: #101319;
  border-bottom: 1px solid #1e222b;
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
}

.brand-mark {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: var(--el-color-primary);
  color: #f5f8ff;
  font-weight: 700;
  display: grid;
  place-items: center;
  font-size: 15px;
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.4px;
}

.merchant-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  background: rgba(64, 158, 255, 0.12);
  border: 1px solid rgba(64, 158, 255, 0.35);
  color: #7ec1ff;
  font-size: 12px;
  white-space: nowrap;
}

.nav {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 8px;
}

.nav-item {
  padding: 6px 12px;
  border-radius: 7px;
  color: var(--el-text-color-secondary);
  font-size: 13.5px;
  transition: all 0.15s ease;
}

.nav-item:hover {
  color: var(--el-text-color-primary);
  background: #181c24;
}

.nav-item.active {
  color: #ffffff;
  background: #1d2330;
}

.search {
  width: 230px;
}

.user {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  border-radius: 7px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-size: 13px;
  outline: none;
}

.user:hover {
  background: #181c24;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-success);
  box-shadow: 0 0 0 3px rgba(62, 207, 142, 0.12);
}

.caret {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.icon-btn {
  color: var(--el-text-color-secondary);
}

.pwd-hint {
  margin-left: 86px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
