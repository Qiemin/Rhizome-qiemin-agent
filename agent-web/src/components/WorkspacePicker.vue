<script setup>
import Icon from './Icon.vue'

const props = defineProps({
  modelValue: { type: String, default: null },
  items: { type: Array, default: () => [] },
  selected: { type: Object, default: null },
  disabled: Boolean,
  loading: Boolean,
  hasMore: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['change', 'manage', 'more', 'refresh'])

function change(event) {
  const value = event.target.value
  // Keep showing the saved binding until the parent confirms the PUT.
  event.target.value = props.modelValue || ''
  if (value === '@more') emit('more')
  else emit('change', value || null)
}
</script>

<template>
  <div class="workspace-picker" :title="selected?.root_path">
    <Icon name="folder" :size="14" />
    <select :value="modelValue || ''" :disabled="disabled || loading" aria-label="会话工作区" @change="change">
      <option value="">{{ loading && !items.length ? '加载工作区…' : '不使用工作区' }}</option>
      <option v-if="modelValue && !items.some(item => item.workspace_id === modelValue)" :value="modelValue">{{ selected?.name || '当前绑定工作区' }}</option>
      <option v-for="item in items" :key="item.workspace_id" :value="item.workspace_id">{{ item.name }}</option>
      <option v-if="hasMore" value="@more">加载更多工作区…</option>
    </select>
    <button v-if="error" type="button" class="icon-button" :disabled="disabled || loading" aria-label="重试加载工作区" :title="error" @click="emit('refresh')"><Icon name="refresh" :size="13" /></button>
    <button type="button" class="icon-button" :disabled="disabled" aria-label="管理工作区" title="管理工作区" @click="emit('manage')"><Icon name="edit" :size="13" /></button>
  </div>
</template>
