<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>小工具</h1>
        <p class="muted small">日常用得到的小功能，会陆续增加。</p>
      </div>
    </div>

    <div class="tool-grid">
      <button class="tool-card" type="button" @click="router.push({ name: 'queue' })">
        <div class="tool-icon queue">
          <el-icon><Tickets /></el-icon>
        </div>
        <div class="tool-body">
          <div class="tool-title">
            排队登记
            <span class="tool-badge">已上线</span>
          </div>
          <p class="tool-desc">
            登记等位的玩家、叫号上机，一键生成排队阵容图发到群里。
          </p>
        </div>
        <el-icon class="tool-go"><ArrowRight /></el-icon>
      </button>

      <button class="tool-card" type="button" @click="router.push({ name: 'name-lists' })">
        <div class="tool-icon names">
          <el-icon><Notebook /></el-icon>
        </div>
        <div class="tool-body">
          <div class="tool-title">
            常用名单
            <span class="tool-badge">已上线</span>
          </div>
          <p class="tool-desc">打手、免茶水、免押金这类名单，随时查、随时改。</p>
        </div>
        <el-icon class="tool-go"><ArrowRight /></el-icon>
      </button>

      <div class="tool-card ghost">
        <div class="tool-icon"><el-icon><Plus /></el-icon></div>
        <div class="tool-body">
          <div class="tool-title">更多工具</div>
          <p class="tool-desc">有想要的小功能，告诉管理员。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, Notebook, Plus, Tickets } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.tool-card {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 18px;
  text-align: left;
  border-radius: 12px;
  border: 1px solid var(--app-border);
  background: var(--app-bg-panel);
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
  font: inherit;
  color: inherit;
}

.tool-card:hover {
  border-color: var(--el-color-primary);
  transform: translateY(-1px);
  box-shadow: var(--app-shadow);
}

.tool-card.ghost {
  cursor: default;
  opacity: 0.7;
}

.tool-card.ghost:hover {
  border-color: var(--app-border);
  transform: none;
  box-shadow: none;
}

.tool-icon {
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 21px;
  background: var(--app-bg-subtle);
  color: var(--app-text-muted);
}

.tool-icon.queue {
  background: rgba(64, 158, 255, 0.12);
  color: var(--el-color-primary);
}

.tool-icon.names {
  background: var(--app-success-soft);
  color: var(--el-color-success);
}

.tool-body {
  flex: 1;
  min-width: 0;
}

.tool-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.tool-badge {
  padding: 0 7px;
  height: 18px;
  line-height: 18px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  color: var(--el-color-success);
  background: var(--app-success-soft);
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.tool-desc {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--app-text-muted);
}

.tool-go {
  flex: none;
  color: var(--app-text-muted);
}

@media (max-width: 768px) {
  .tool-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
