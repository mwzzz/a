<template>
  <div class="page name-list-view">
    <div class="page-head">
      <div>
        <h1>常用名单</h1>
        <p class="muted small">打手、免茶水、免押金这类店铺规矩，随时可查可改。</p>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateList">新建分类</el-button>
      </div>
    </div>

    <div v-loading="loading" class="list-grid">
      <section v-for="list in lists" :key="list.id" class="list-card">
        <header class="card-head">
          <div class="card-title">
            <b>{{ list.name }}</b>
            <span class="muted small">{{ list.items.length }} 条</span>
          </div>
          <div class="card-ops">
            <el-button link :icon="Top" :disabled="list.id === lists[0]?.id" @click="moveList(list, 'up')" />
            <el-button
              link
              :icon="Bottom"
              :disabled="list.id === lists[lists.length - 1]?.id"
              @click="moveList(list, 'down')"
            />
            <el-button link :icon="EditPen" @click="openRenameList(list)" />
            <el-button link type="danger" :icon="Delete" @click="removeList(list)" />
          </div>
        </header>

        <div v-if="list.items.length" class="item-list">
          <div v-for="(item, index) in list.items" :key="item.id" class="item-row">
            <span class="item-index">{{ index + 1 }}</span>
            <div class="item-main">
              <div class="item-content" @click="openEditItem(list, item)">{{ item.content }}</div>
              <div v-if="item.note" class="item-note">{{ item.note }}</div>
            </div>
            <div class="item-ops">
              <el-button
                link
                :icon="Top"
                :disabled="index === 0"
                @click="moveItem(list, item, 'up')"
              />
              <el-button
                link
                :icon="Bottom"
                :disabled="index === list.items.length - 1"
                @click="moveItem(list, item, 'down')"
              />
              <el-button link type="danger" :icon="Close" @click="removeItem(list, item)" />
            </div>
          </div>
        </div>
        <div v-else class="empty-hint">还没有条目</div>

        <div class="add-row">
          <el-input
            v-model="drafts[list.id]"
            size="small"
            maxlength="64"
            placeholder="输入名字后回车添加"
            @keyup.enter="addItem(list)"
          />
          <el-button size="small" type="primary" plain :icon="Plus" @click="addItem(list)">
            添加
          </el-button>
        </div>
      </section>

      <el-empty v-if="!loading && !lists.length" description="还没有分类，点右上角新建" />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="400px" :close-on-click-modal="false">
      <el-form label-width="64px">
        <el-form-item :label="dialogMode === 'item' ? '内容' : '名称'" required>
          <el-input
            v-model="form.name"
            maxlength="64"
            :placeholder="dialogMode === 'item' ? '例如：能天使' : '例如：免茶水'"
            @keyup.enter="submitDialog"
          />
        </el-form-item>
        <el-form-item v-if="dialogMode === 'item'" label="备注">
          <el-input v-model="form.note" maxlength="100" placeholder="选填" @keyup.enter="submitDialog" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitDialog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Bottom, Close, Delete, EditPen, Plus, Refresh, Top } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { toolListApi } from '@/api'
import type { ToolItemRow, ToolListRow } from '@/api/types'

const loading = ref(false)
const saving = ref(false)
const lists = ref<ToolListRow[]>([])
const drafts = reactive<Record<number, string>>({})

const dialogVisible = ref(false)
const dialogMode = ref<'list' | 'rename' | 'item'>('list')
const dialogTitle = ref('新建分类')
const form = reactive({ name: '', note: '' })
const target = reactive<{ listId: number; itemId: number | null }>({ listId: 0, itemId: null })

async function load() {
  loading.value = true
  try {
    const payload = await toolListApi.list()
    lists.value = payload.lists
    for (const list of payload.lists) {
      if (drafts[list.id] === undefined) drafts[list.id] = ''
    }
  } finally {
    loading.value = false
  }
}

function openCreateList() {
  dialogMode.value = 'list'
  dialogTitle.value = '新建分类'
  form.name = ''
  form.note = ''
  dialogVisible.value = true
}

function openRenameList(list: ToolListRow) {
  dialogMode.value = 'rename'
  dialogTitle.value = `重命名「${list.name}」`
  form.name = list.name
  form.note = ''
  target.listId = list.id
  dialogVisible.value = true
}

function openEditItem(list: ToolListRow, item: ToolItemRow) {
  dialogMode.value = 'item'
  dialogTitle.value = '编辑条目'
  form.name = item.content
  form.note = item.note
  target.listId = list.id
  target.itemId = item.id
  dialogVisible.value = true
}

async function submitDialog() {
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('请填写内容')
    return
  }
  saving.value = true
  try {
    if (dialogMode.value === 'list') {
      await toolListApi.createList(name)
      ElMessage.success('分类已创建')
    } else if (dialogMode.value === 'rename') {
      await toolListApi.renameList(target.listId, name)
      ElMessage.success('已重命名')
    } else if (target.itemId) {
      await toolListApi.updateItem(target.listId, target.itemId, {
        content: name,
        note: form.note.trim(),
      })
      ElMessage.success('已保存')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function removeList(list: ToolListRow) {
  try {
    await ElMessageBox.confirm(
      `删除分类「${list.name}」会一起删掉里面的 ${list.items.length} 条记录，确定吗？`,
      '删除分类',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await toolListApi.deleteList(list.id)
  ElMessage.success('已删除')
  await load()
}

async function moveList(list: ToolListRow, direction: 'up' | 'down') {
  const payload = await toolListApi.moveList(list.id, direction)
  lists.value = payload.lists
}

async function addItem(list: ToolListRow) {
  const content = (drafts[list.id] || '').trim()
  if (!content) {
    ElMessage.warning('先输入名字')
    return
  }
  await toolListApi.createItem(list.id, content)
  drafts[list.id] = ''
  await load()
}

async function removeItem(list: ToolListRow, item: ToolItemRow) {
  await toolListApi.deleteItem(list.id, item.id)
  await load()
}

async function moveItem(list: ToolListRow, item: ToolItemRow, direction: 'up' | 'down') {
  await toolListApi.moveItem(list.id, item.id, direction)
  await load()
}

onMounted(load)
</script>

<style scoped>
.list-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
  align-items: start;
}

.list-card {
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-bg-panel);
  padding: 14px 16px 12px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.card-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.card-title b {
  font-size: 15px;
}

.card-ops {
  display: flex;
  gap: 2px;
  flex: none;
}

.card-ops :deep(.el-button) {
  margin-left: 0;
  padding: 4px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 6px;
  border-radius: 8px;
}

.item-row:hover {
  background: var(--app-bg-hover);
}

.item-index {
  flex: none;
  width: 20px;
  text-align: right;
  font-size: 12px;
  color: var(--app-text-faint);
  font-variant-numeric: tabular-nums;
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-content {
  font-size: 13.5px;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-note {
  font-size: 11.5px;
  color: var(--app-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-ops {
  display: flex;
  gap: 0;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.item-row:hover .item-ops {
  opacity: 1;
}

.item-ops :deep(.el-button) {
  margin-left: 0;
  padding: 2px;
}

.add-row {
  display: flex;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--app-border);
}

@media (max-width: 768px) {
  .list-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .item-ops {
    opacity: 1;
  }
}
</style>
