<script setup>
import { nextTick, reactive, ref, watch } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  loading: Boolean,
  saving: Boolean,
  disabled: Boolean,
  hasMore: Boolean,
  error: { type: String, default: '' },
  saveWorkspace: { type: Function, required: true },
})
const emit = defineEmits(['select', 'refresh', 'more'])
const dialog = ref(null)
const nameInput = ref(null)
const editingId = ref(null)
const formError = ref('')
const form = reactive({ name: '', root_path: '', writable: false, terminal: false })
watch(() => form.writable, writable => { if (!writable) form.terminal = false })

async function open(item = null) {
  editingId.value = item?.workspace_id || null
  formError.value = ''
  Object.assign(form, {
    name: item?.name || '', root_path: item?.root_path || '',
    writable: item?.writable || false, terminal: item?.execution_mode === 'local',
  })
  dialog.value.showModal()
  await nextTick()
  nameInput.value?.focus()
}

function cancel(event) {
  if (props.saving) event.preventDefault()
}

async function submit() {
  if (props.saving || props.loading || !form.name.trim() || !form.root_path.trim()) return
  formError.value = ''
  const body = {
    name: form.name.trim(), writable: form.writable,
    execution_mode: form.writable && form.terminal ? 'local' : 'disabled',
  }
  if (!editingId.value) body.root_path = form.root_path.trim()
  try {
    if (await props.saveWorkspace(body, editingId.value)) dialog.value.close()
  } catch (error) { formError.value = error.message }
}
</script>

<template>
  <section class="workspace-section" aria-labelledby="workspace-heading">
    <div class="workspace-heading">
      <h2 id="workspace-heading">工作区</h2>
      <div class="workspace-heading-actions">
        <button class="icon-button" aria-label="刷新工作区" :disabled="disabled || loading || saving" @click="emit('refresh')"><Icon name="refresh" :size="16" /></button>
        <button class="secondary-button" :disabled="disabled || loading || saving" @click="open()"><Icon name="plus" :size="14" />添加工作区</button>
      </div>
    </div>
    <div v-if="error" class="workspace-error" role="alert"><span>{{ error }}</span><button class="secondary-button" :disabled="loading || saving" @click="emit('refresh')">重试</button></div>
    <div v-if="loading && !items.length" class="loading-state" role="status"><span class="spinner" /><span class="sr-only">加载工作区</span></div>
    <p v-else-if="!items.length && !error" class="empty-state">暂无工作区</p>
    <div v-else class="workspace-list">
      <article v-for="item in items" :key="item.workspace_id" class="workspace-card" :class="{ selected: selectedId === item.workspace_id }">
        <span class="workspace-symbol"><Icon name="folder" :size="20" /></span>
        <div class="workspace-info"><h3>{{ item.name }}</h3><p :title="item.root_path">{{ item.root_path }}</p><div class="workspace-badges"><span>{{ item.writable ? '允许写入' : '只读' }}</span><span :class="{ enabled: item.execution_mode === 'local' }">{{ item.execution_mode === 'local' ? '终端已启用' : '终端已关闭' }}</span></div></div>
        <div class="workspace-card-actions">
          <button class="icon-button" :aria-label="`编辑工作区 ${item.name}`" title="设置" :disabled="disabled || saving || loading" @click="open(item)"><Icon name="edit" :size="16" /></button>
          <button class="secondary-button" :disabled="disabled || saving || loading || selectedId === item.workspace_id" @click="emit('select', item.workspace_id)">{{ selectedId === item.workspace_id ? '已选择' : '使用' }}<Icon v-if="selectedId !== item.workspace_id" name="arrowRight" :size="13" /><Icon v-else name="check" :size="13" /></button>
        </div>
      </article>
    </div>
    <button v-if="hasMore" class="load-more" :disabled="loading || saving" @click="emit('more')">{{ loading ? '加载中…' : '加载更多' }}</button>
  </section>

  <dialog ref="dialog" class="workspace-dialog acrylic" aria-labelledby="workspace-dialog-title" @cancel="cancel">
    <form @submit.prevent="submit">
      <div class="workspace-dialog-heading"><h2 id="workspace-dialog-title">{{ editingId ? '工作区设置' : '添加工作区' }}</h2><button class="icon-button" type="button" aria-label="关闭工作区设置" :disabled="saving" @click="dialog.close()"><Icon name="close" :size="17" /></button></div>
      <label class="workspace-field"><span>名称</span><input ref="nameInput" v-model="form.name" name="name" maxlength="200" required :disabled="saving" autocomplete="off" /></label>
      <label class="workspace-field"><span>目录</span><input v-model="form.root_path" name="root_path" placeholder="D:\工作资料" maxlength="4096" required :readonly="!!editingId" :disabled="saving" autocomplete="off" :aria-describedby="editingId ? 'workspace-path-hint' : undefined" /></label>
      <p v-if="editingId" id="workspace-path-hint" class="workspace-field-hint">目录不可修改；其他目录请添加为新工作区。</p>
      <div class="workspace-permissions">
        <label><input v-model="form.writable" type="checkbox" :disabled="saving" /><span>允许写入</span></label>
        <label><input v-model="form.terminal" type="checkbox" :disabled="saving || !form.writable" aria-describedby="workspace-terminal-hint" /><span>启用本地终端</span></label>
        <p id="workspace-terminal-hint">终端以当前系统用户权限运行，可访问该用户有权限的其他目录。</p>
      </div>
      <p v-if="formError" class="workspace-form-error" role="alert">{{ formError }}</p>
      <div class="dialog-actions"><button class="secondary-button" type="button" :disabled="saving" @click="dialog.close()">取消</button><button class="primary-button" type="submit" :disabled="saving || loading || !form.name.trim() || !form.root_path.trim()">{{ saving ? '保存中…' : '保存' }}</button></div>
    </form>
  </dialog>
</template>
