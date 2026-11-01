<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <span class="brand-mark">L</span>
        <div>
          <div class="brand-title">LOL 记录管理</div>
          <div class="brand-sub">押金 · 场次 · 班次对账</div>
        </div>
      </div>

      <el-form class="form" @submit.prevent="submit">
        <el-form-item>
          <el-input
            v-model="username"
            size="large"
            placeholder="用户名"
            autocomplete="username"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            size="large"
            type="password"
            placeholder="密码"
            show-password
            autocomplete="current-password"
            :prefix-icon="Lock"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button class="submit" type="primary" size="large" :loading="loading" @click="submit">
          登录
        </el-button>
      </el-form>

      <div class="foot">账号由管理员分配，忘记密码请联系店长重置。</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(900px 500px at 50% -10%, rgba(76, 141, 255, 0.12), transparent 60%),
    #0b0d12;
  padding: 24px;
}

.login-card {
  width: 380px;
  padding: 30px 30px 24px;
  background: #14161c;
  border: 1px solid #232833;
  border-radius: 14px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 26px;
}

.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--el-color-primary);
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
  display: grid;
  place-items: center;
}

.brand-title {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.brand-sub {
  margin-top: 3px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.submit {
  width: 100%;
  margin-top: 4px;
}

.foot {
  margin-top: 20px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
</style>
