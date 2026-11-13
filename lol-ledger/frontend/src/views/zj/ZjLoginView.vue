<template>
  <div class="zj-login">
    <div class="zj-login-card">
      <div class="brand">
        <span class="brand-mark">Z</span>
        <div>
          <div class="brand-title">新模式战队战绩</div>
          <div class="brand-sub">粘贴队伍玩家 → 逐个查询 → 统计新模式</div>
        </div>
      </div>

      <form class="form" @submit.prevent="submit">
        <label class="field">
          <span>用户名</span>
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            placeholder="由管理员分配"
            :disabled="loading"
          />
        </label>
        <label class="field">
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="初始密码找管理员要"
            :disabled="loading"
          />
        </label>

        <button class="submit" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>

      <p class="foot">
        账号与查询次数由管理员在「平台管理 → 查战绩配额」里分配；忘记密码请联系管理员重置。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { zjErrorMessage } from '@/api/zj'
import { useZjAuthStore } from '@/stores/zjAuth'

const route = useRoute()
const router = useRouter()
const auth = useZjAuthStore()

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
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/zj'
    await router.replace(redirect.startsWith('/zj') ? redirect : '/zj')
  } catch (error) {
    ElMessage.error(zjErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.zj-login {
  min-height: 100%;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(720px 420px at 50% 0%, rgba(76, 141, 255, 0.16), transparent 62%),
    var(--app-bg-page);
}

.zj-login-card {
  width: 380px;
  max-width: 100%;
  padding: 30px 30px 24px;
  background: var(--app-bg-panel);
  border: 1px solid var(--app-border);
  border-radius: 16px;
  box-shadow: var(--app-shadow);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 26px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: linear-gradient(135deg, #4c8dff, #2f6bff);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  box-shadow: 0 8px 22px rgba(47, 107, 255, 0.35);
}

.brand-title {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.4px;
}

.brand-sub {
  margin-top: 3px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.field input {
  height: 42px;
  padding: 0 12px;
  border: 1px solid var(--app-border);
  border-radius: 9px;
  background: var(--app-bg-subtle);
  color: var(--el-text-color-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.field input:focus {
  border-color: #4c8dff;
  box-shadow: 0 0 0 3px rgba(76, 141, 255, 0.16);
}

.submit {
  margin-top: 8px;
  height: 44px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #4c8dff, #2f6bff);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  transition: filter 0.16s ease, transform 0.16s ease;
}

.submit:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.foot {
  margin: 20px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--app-text-muted);
}

@media (max-width: 480px) {
  .zj-login {
    padding: 12px;
  }

  .zj-login-card {
    width: 100%;
    padding: 24px 18px 18px;
  }
}
</style>
