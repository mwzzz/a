<template>
  <div v-if="!auth.isSuperadmin" class="shift-strip">
    <div class="shift-left">
      <span class="pulse"></span>
      <template v-if="app.todayError">
        <b class="strip-error">今日数据暂不可用</b>
        <span class="muted">请检查网络或服务</span>
        <el-button link type="primary" size="small" @click="app.refreshToday()">重试</el-button>
      </template>
      <template v-else-if="app.todayLoading && !app.today">
        <span class="muted">加载中…</span>
      </template>
      <template v-else-if="app.today">
        <b>今日</b>
        <span>{{ app.today.session_count }} 局</span>
        <span class="sep">·</span>
        <span>茶水 <b class="cash">¥{{ formatCents(app.today.tea_cents) }}</b></span>
        <span class="sep">·</span>
        <span class="muted">
          收押金 ¥{{ formatCents(app.today.add_deposit_cents) }} / 退
          ¥{{ formatCents(app.today.refund_cents) }}
        </span>
      </template>
      <template v-else-if="app.todayLoaded">
        <b>今日还没有记录</b>
        <span class="muted">开一局后这里会显示</span>
      </template>
      <template v-else>
        <span class="muted">加载中…</span>
      </template>
    </div>
    <div class="shift-right">
      <el-button size="small" type="primary" @click="openSession">开一局</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { formatCents } from '@/utils/money'

const app = useAppStore()
const auth = useAuthStore()

function openSession() {
  app.openSessionDialog()
}
</script>

<style scoped>
.shift-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 36px;
  padding: 5px 22px;
  background: var(--app-bg-panel);
  border-bottom: 1px solid var(--app-border);
  font-size: 12.5px;
  color: var(--el-text-color-regular);
  position: sticky;
  top: 56px;
  z-index: 19;
}

.shift-left {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  flex-wrap: wrap;
}

.shift-left b {
  font-weight: 600;
}

.cash {
  color: var(--el-color-success);
  font-variant-numeric: tabular-nums;
}

.strip-error {
  color: var(--el-color-danger);
}

.sep {
  color: var(--app-border-strong);
}

.pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-success);
  box-shadow: 0 0 0 3px var(--app-success-soft);
  flex: none;
}

.shift-right {
  margin-left: auto;
  flex: none;
}

@media (max-width: 768px) {
  .shift-strip {
    top: 52px;
    padding: 5px 14px;
    font-size: 12px;
  }

  .shift-left .sep {
    display: none;
  }
}
</style>
