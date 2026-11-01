<script setup>
import Icon from './Icon.vue'
defineProps({ message: { type: Object, required: true } })
const emit = defineEmits(['notice'])
async function copy(text) {
  try { await navigator.clipboard.writeText(text); emit('notice', '已复制') }
  catch { emit('notice', '复制失败，请选择文字复制') }
}
</script>

<template>
  <details v-if="message.role === 'tool'" class="tool-message">
    <summary><Icon name="code" :size="14" />{{ message.name || '工具结果' }}<Icon name="down" :size="12" /></summary>
    <pre>{{ message.content }}</pre>
  </details>
  <article v-else-if="message.content || message.status || !message.tool_calls?.length" class="message" :class="message.role" :aria-label="message.role === 'assistant' ? 'Rhizome 回复' : '你的消息'">
    <div class="message-main">
      <div :class="message.role === 'user' ? 'message-bubble' : 'message-body'">
        <div class="message-content">{{ message.content }}<span v-if="message.status === 'streaming' && message.content" class="stream-cursor" /></div>
        <div v-if="message.status === 'streaming' && !message.content" class="thinking"><i /><i /><i /><span class="sr-only">正在思考</span></div>
        <span v-if="message.status === 'error'" class="message-state error">回复中断</span>
        <span v-if="message.status === 'stopped'" class="message-state">已停止接收</span>
      </div>
      <div v-if="message.role === 'assistant' && message.content && message.status !== 'streaming'" class="message-actions">
        <button class="icon-button copy-button" title="复制" aria-label="复制回复" @click="copy(message.content)"><Icon name="copy" :size="14" /></button>
      </div>
    </div>
  </article>
</template>
