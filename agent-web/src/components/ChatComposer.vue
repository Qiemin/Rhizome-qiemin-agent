<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import Icon from './Icon.vue'
import BrandMark from './BrandMark.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  busy: Boolean,
  loading: Boolean,
  streaming: Boolean,
})
const emit = defineEmits(['update:modelValue', 'send', 'stop'])
const input = ref(null)

function resize() {
  if (!input.value) return
  input.value.style.height = 'auto'
  input.value.style.height = `${Math.min(Math.max(input.value.scrollHeight, 94), 220)}px`
}
function keydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    if (!props.busy && !props.loading && props.modelValue.trim()) emit('send')
  }
}
function focus() { input.value?.focus() }
watch(() => props.modelValue, async () => { await nextTick(); resize() })
onMounted(resize)
defineExpose({ focus })
</script>

<template>
  <form class="composer" :class="{ generating: streaming }" @submit.prevent="emit('send')">
    <textarea
      ref="input"
      :value="modelValue"
      aria-label="描述你的任务"
      placeholder="描述你的任务…"
      maxlength="32000"
      rows="3"
      @input="emit('update:modelValue', $event.target.value)"
      @keydown="keydown"
    />
    <div class="composer-bottom">
      <div class="composer-tools">
        <span class="agent-label"><BrandMark class="agent-symbol" label="工作室标志" />通用 Agent</span>
        <slot name="workspace" />
      </div>
      <div class="submit-area">
        <span class="input-hint">Enter 发送 · Shift + Enter 换行</span>
        <button v-if="streaming" class="send-button stop-button" type="button" aria-label="停止接收回复" title="停止接收" @click="emit('stop')"><span /></button>
        <button v-else class="send-button" type="submit" :disabled="busy || loading || !modelValue.trim()" aria-label="发送消息" title="发送"><Icon name="arrow" :size="19" /></button>
      </div>
    </div>
  </form>
</template>
