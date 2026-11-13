<template>
  <nav v-if="!auth.isSuperadmin" class="bottom-nav">
    <router-link
      v-for="item in items"
      :key="item.name"
      :to="{ name: item.name }"
      class="bottom-item"
      active-class="active"
    >
      <el-icon><component :is="item.icon" /></el-icon>
      <span>{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { Calendar, DataBoard, MagicStick, Setting, TrendCharts, User } from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const items = [
  { name: 'overview', label: '工作台', icon: DataBoard },
  { name: 'summary', label: '汇总', icon: Calendar },
  { name: 'players', label: '玩家', icon: User },
  { name: 'reports', label: '报表', icon: TrendCharts },
  { name: 'settings', label: '设置', icon: Setting },
  { name: 'tools', label: '小工具', icon: MagicStick },
]
</script>

<style scoped>
.bottom-nav {
  display: none;
}

@media (max-width: 768px) {
  .bottom-nav {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 30;
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    padding: 6px 4px calc(6px + env(safe-area-inset-bottom));
    background: color-mix(in srgb, var(--app-bg-panel) 92%, transparent);
    backdrop-filter: blur(12px);
    border-top: 1px solid var(--app-border);
  }

  .bottom-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 4px 0;
    font-size: 10.5px;
    color: var(--app-text-muted);
    border-radius: 8px;
  }

  .bottom-item .el-icon {
    font-size: 19px;
  }

  .bottom-item.active {
    color: var(--el-color-primary);
    font-weight: 600;
  }
}
</style>
