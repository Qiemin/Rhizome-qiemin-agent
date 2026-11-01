<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import BrandMark from './components/BrandMark.vue'
import ChatComposer from './components/ChatComposer.vue'
import Icon from './components/Icon.vue'
import MessageBubble from './components/MessageBubble.vue'
import WorkspaceManager from './components/WorkspaceManager.vue'
import WorkspacePicker from './components/WorkspacePicker.vue'
import { useChat } from './composables/useChat.js'
import { useSidebarResize } from './composables/useSidebarResize.js'
import { useWorkspaces } from './composables/useWorkspaces.js'

const chat = useChat()
const { sessions, total, activeSession, workspaceId, messages, busy, streaming, loading, notice, hasMore } = chat
const workspaces = useWorkspaces()
const { items: workspaceItems, loading: workspacesLoading, saving: workspacesSaving, error: workspacesError, hasMore: hasMoreWorkspaces } = workspaces
const selectedWorkspace = computed(() => workspaces.get(workspaceId.value))
const view = ref('home')
const draft = ref('')
const search = ref('')
const sidebarOpen = ref(false)
const { sidebarWidth, sidebarMinWidth, sidebarMaxWidth, resizingSidebar, startSidebarResize, moveSidebarResize, stopSidebarResize, resizeSidebarWithKeyboard } = useSidebarResize()
const composer = ref(null)
const messageList = ref(null)
const editDialog = ref(null)
const searchDialog = ref(null)
const searchInput = ref(null)
const titleInput = ref(null)
const editKind = ref('rename')
const titleDraft = ref('')
const loadingMore = ref(false)

function savedTheme() {
  try { return localStorage.getItem('rhizome.theme') === 'dark' ? 'dark' : 'light' }
  catch { return 'light' }
}
const theme = ref(savedTheme())
watch(theme, value => {
  document.documentElement.dataset.theme = value
  try { localStorage.setItem('rhizome.theme', value) } catch {}
}, { immediate: true })

const navigation = [
  { id: 'home', label: '工作台', icon: 'home' },
  { id: 'agents', label: '我的 Agent' },
  { id: 'history', label: '会话记录', icon: 'history' },
  { id: 'resources', label: '资源库', icon: 'folder' },
]
const visibleMessages = computed(() => messages.value.filter(item => item.role !== 'system'))
const filtered = computed(() => sessions.value.filter(item => item.title.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase())))
const currentTitle = computed(() => (view.value === 'chat' || (view.value === 'home' && activeSession.value)) ? activeSession.value?.title || '新会话' : navigation.find(item => item.id === view.value)?.label || '工作台')

function closeSidebar() { sidebarOpen.value = false }
async function navigate(next) {
  if (busy.value) return
  view.value = next
  closeSidebar()
  if (next === 'home') { chat.resetSession(); await nextTick(); composer.value?.focus() }
  if (next === 'resources' && (!workspaces.loaded.value || workspacesError.value)) await workspaces.refresh()
}
async function chooseWorkspace(id) {
  if (!await chat.selectWorkspace(id)) return
  if (view.value === 'resources') view.value = activeSession.value && messages.value.length ? 'chat' : 'home'
  await nextTick()
  composer.value?.focus()
}
async function saveWorkspace(body, id) {
  const item = await workspaces.save(body, id)
  if (item) chat.notify(id ? '工作区设置已保存' : '工作区已添加')
  return item
}
async function create() {
  if (busy.value || loading.value) return
  view.value = 'home'
  closeSidebar()
  await chat.createSession()
  await nextTick()
  composer.value?.focus()
}
async function select(id) {
  if (busy.value) return
  closeSidebar()
  searchDialog.value?.close()
  await chat.openSession(id)
  if (activeSession.value?.session_id === id) view.value = messages.value.length ? 'chat' : 'home'
}
async function submit() {
  if (busy.value || loading.value || !draft.value.trim()) return
  const text = draft.value
  draft.value = ''
  view.value = 'chat'
  const accepted = await chat.sendMessage(text)
  if (!accepted) {
    if (!draft.value) draft.value = text
    view.value = 'home'
  }
}
async function loadMore() {
  if (loadingMore.value || busy.value) return
  loadingMore.value = true
  try { await chat.refreshSessions(true) } catch (error) { chat.notify(error.message) }
  finally { loadingMore.value = false }
}
async function openSearch() {
  if (busy.value) return
  search.value = ''
  searchDialog.value.showModal()
  await nextTick()
  searchInput.value?.focus()
}
async function openEdit(kind) {
  editKind.value = kind
  titleDraft.value = activeSession.value?.title || ''
  editDialog.value.showModal()
  if (kind === 'rename') { await nextTick(); titleInput.value?.select() }
}
async function confirmEdit() {
  if (editKind.value === 'rename' && !titleDraft.value.trim()) return
  const success = editKind.value === 'rename'
    ? await chat.renameSession(titleDraft.value.trim())
    : await chat.deleteSession()
  if (success) {
    editDialog.value.close()
    if (editKind.value === 'delete') view.value = 'home'
  }
}
function dateLabel(value) {
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(new Date(value))
}
function shortcuts(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault(); openSearch(); return
  }
  if (event.key === 'Escape') closeSidebar()
  const editable = ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName) || event.target.isContentEditable
  if (event.key.toLowerCase() === 'n' && !editable && !event.ctrlKey && !event.metaKey && !event.altKey && !document.querySelector('dialog[open]')) {
    event.preventDefault(); create()
  }
}
watch(() => messages.value.map(item => `${item.id}:${item.content?.length}`).join('|'), async () => {
  const element = messageList.value
  const follow = !element || element.scrollHeight - element.scrollTop - element.clientHeight < 150
  await nextTick()
  if (follow && messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
})
watch(() => activeSession.value?.session_id, async () => {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
})
watch(workspaceId, async id => {
  if (!id) return
  try { await workspaces.resolve(id) }
  catch (error) { chat.notify(error.message) }
})
onMounted(async () => {
  window.addEventListener('keydown', shortcuts)
  await Promise.all([chat.initialize(), workspaces.refresh()])
  if (activeSession.value && messages.value.length) view.value = 'chat'
})
onUnmounted(() => window.removeEventListener('keydown', shortcuts))
</script>

<template>
  <div class="workspace" :class="{ 'resizing-sidebar': resizingSidebar }" :data-theme="theme" :style="{ '--sidebar-width': `${sidebarWidth}px` }">
    <button v-if="sidebarOpen" class="sidebar-backdrop" aria-label="关闭导航" @click="closeSidebar" />
    <aside id="sidebar" class="sidebar acrylic" :class="{ open: sidebarOpen }" aria-label="主导航">
      <button class="brand" aria-label="Rhizome 工作台" :disabled="busy" @click="navigate('home')"><BrandMark /><span>Rhizome</span></button>
      <button class="new-task" :disabled="busy || loading" @click="create"><Icon name="plus" :size="18" /><span>新建任务</span><kbd>N</kbd></button>
      <nav class="primary-nav" aria-label="工作空间导航">
        <button v-for="item in navigation" :key="item.id" class="nav-button" :class="{ active: view === item.id || (view === 'chat' && item.id === 'history') }" :aria-current="view === item.id || (view === 'chat' && item.id === 'history') ? 'page' : undefined" :disabled="busy" @click="navigate(item.id)">
          <BrandMark v-if="item.id === 'agents'" class="nav-agent-symbol" label="工作室标志" /><Icon v-else :name="item.icon" :size="19" /><span>{{ item.label }}</span><span v-if="item.id === 'agents'" class="nav-count">1</span>
        </button>
      </nav>
      <div class="nav-label">最近会话</div>
      <nav class="recent-nav" aria-label="最近会话">
        <button v-for="item in sessions.slice(0, 6)" :key="item.session_id" class="recent-button" :class="{ selected: activeSession?.session_id === item.session_id && view === 'chat' }" :disabled="busy" :title="item.title" @click="select(item.session_id)"><span class="session-dot" /><span>{{ item.title }}</span></button>
        <span v-if="!sessions.length" class="empty-recent">{{ loading ? '加载中…' : '暂无会话' }}</span>
      </nav>
      <div class="sidebar-bottom"><div class="account"><span class="account-avatar">R</span><span class="account-info"><strong>你的工作空间</strong><span>本地空间</span></span><button class="icon-button" aria-label="重新连接" title="重新连接" :disabled="busy || loading" @click="chat.initialize"><Icon name="refresh" :size="15" /></button></div></div>
      <div
        class="sidebar-resizer"
        role="separator"
        tabindex="0"
        aria-label="调整侧栏宽度"
        aria-orientation="vertical"
        aria-controls="sidebar"
        :aria-valuemin="sidebarMinWidth"
        :aria-valuemax="sidebarMaxWidth"
        :aria-valuenow="sidebarWidth"
        :aria-valuetext="`${sidebarWidth} 像素`"
        title="拖动调整侧栏宽度"
        @pointerdown="startSidebarResize"
        @pointermove="moveSidebarResize"
        @pointerup="stopSidebarResize"
        @pointercancel="stopSidebarResize"
        @lostpointercapture="stopSidebarResize"
        @keydown="resizeSidebarWithKeyboard"
      />
    </aside>

    <main class="main-panel">
      <header class="topbar acrylic">
        <div class="breadcrumbs"><button class="icon-button menu-button" aria-label="打开导航" :aria-expanded="sidebarOpen" aria-controls="sidebar" @click="sidebarOpen = !sidebarOpen"><Icon name="menu" /></button><Icon class="breadcrumb-icon" name="folder" :size="15" /><span class="space-label">个人空间</span><span class="slash">/</span><span class="current-title">{{ currentTitle }}</span></div>
        <div class="top-actions">
          <template v-if="activeSession && (view === 'chat' || view === 'home')"><button class="icon-button" aria-label="重命名会话" title="重命名" :disabled="busy || loading" @click="openEdit('rename')"><Icon name="edit" :size="17" /></button><button class="icon-button danger-icon" aria-label="删除会话" title="删除" :disabled="busy || loading" @click="openEdit('delete')"><Icon name="trash" :size="17" /></button></template>
          <span class="top-divider" />
          <button class="icon-button" aria-label="搜索会话" title="搜索 · Ctrl K" :disabled="busy" @click="openSearch"><Icon name="search" :size="18" /></button>
          <button class="icon-button theme-toggle" :aria-label="theme === 'light' ? '切换深色' : '切换浅色'" :title="theme === 'light' ? '深色' : '浅色'" @click="theme = theme === 'light' ? 'dark' : 'light'"><Icon :name="theme === 'light' ? 'moon' : 'sun'" :size="18" /></button>
        </div>
      </header>

      <section v-if="view === 'home'" class="home-view" aria-label="工作台">
        <div class="home-content">
          <BrandMark class="hero-symbol" />
          <ChatComposer ref="composer" v-model="draft" :busy="busy" :loading="loading" :streaming="streaming" @send="submit" @stop="chat.stop"><template #workspace><WorkspacePicker :model-value="workspaceId" :items="workspaceItems" :selected="selectedWorkspace" :disabled="busy || loading" :loading="workspacesLoading" :has-more="hasMoreWorkspaces" :error="workspacesError" @change="chooseWorkspace" @manage="navigate('resources')" @more="workspaces.refresh(true)" @refresh="workspaces.refresh()" /></template></ChatComposer>
        </div>
      </section>

      <section v-else-if="view === 'chat'" class="chat-view" aria-label="当前会话">
        <div ref="messageList" class="message-scroll" :aria-busy="loading"><div class="messages"><div v-if="loading" class="loading-state"><span class="spinner" /><span class="sr-only">加载中</span></div><MessageBubble v-for="message in visibleMessages" :key="message.id" :message="message" @notice="chat.notify" /></div></div>
        <div class="chat-composer"><ChatComposer ref="composer" v-model="draft" :busy="busy" :loading="loading" :streaming="streaming" @send="submit" @stop="chat.stop"><template #workspace><WorkspacePicker :model-value="workspaceId" :items="workspaceItems" :selected="selectedWorkspace" :disabled="busy || loading" :loading="workspacesLoading" :has-more="hasMoreWorkspaces" :error="workspacesError" @change="chooseWorkspace" @manage="navigate('resources')" @more="workspaces.refresh(true)" @refresh="workspaces.refresh()" /></template></ChatComposer></div>
      </section>

      <section v-else-if="view === 'history'" class="page-view">
        <div class="page-heading"><h1>会话记录<span class="page-count">{{ total }}</span></h1><button class="icon-button" aria-label="刷新会话" :disabled="loading || busy" @click="chat.initialize"><Icon name="refresh" :size="17" /></button></div>
        <div class="history-list"><button v-for="item in sessions" :key="item.session_id" class="history-row" :disabled="busy" @click="select(item.session_id)"><span class="history-symbol"><Icon name="chat" :size="18" /></span><span class="history-info"><strong>{{ item.title }}</strong><span>{{ item.message_count }} 条消息<span class="tiny-dot" />{{ dateLabel(item.updated_at) }}</span></span><Icon name="chevron" :size="15" /></button><p v-if="!sessions.length" class="empty-state">暂无会话</p></div>
        <button v-if="hasMore" class="load-more" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button>
      </section>

      <section v-else-if="view === 'agents'" class="page-view">
        <div class="page-heading"><h1>我的 Agent</h1></div>
        <div class="agent-card acrylic"><BrandMark /><div><h2>通用 Agent</h2><span class="agent-badge">默认</span></div><button class="secondary-button" :disabled="busy" @click="create">开始任务<Icon name="arrowRight" :size="14" /></button></div>
        <a class="quiet-link" href="/docs" target="_blank" rel="noopener"><Icon name="book" :size="14" />API 文档<Icon name="diagonal" :size="12" /></a>
      </section>

      <section v-else-if="view === 'resources'" class="page-view">
        <div class="page-heading"><h1>资源库</h1></div>
        <WorkspaceManager :items="workspaceItems" :selected-id="workspaceId" :loading="workspacesLoading" :saving="workspacesSaving" :disabled="busy || loading" :has-more="hasMoreWorkspaces" :error="workspacesError" :save-workspace="saveWorkspace" @select="chooseWorkspace" @refresh="workspaces.refresh()" @more="workspaces.refresh(true)" />
      </section>
    </main>

    <Transition name="toast"><div v-if="notice" class="toast-message" role="status" aria-live="polite"><span>{{ notice }}</span><button class="icon-button" aria-label="关闭提示" @click="notice = ''"><Icon name="close" :size="15" /></button></div></Transition>

    <dialog ref="searchDialog" class="search-dialog acrylic" aria-label="搜索会话"><div class="search-input-row"><Icon name="search" :size="19" /><input ref="searchInput" v-model="search" type="search" placeholder="搜索会话…" aria-label="搜索会话关键词" @keydown.enter.prevent="filtered[0] && select(filtered[0].session_id)" /><kbd>Esc</kbd><button class="icon-button" aria-label="关闭搜索" @click="searchDialog.close()"><Icon name="close" :size="17" /></button></div><div class="search-results"><button v-for="item in filtered" :key="item.session_id" @click="select(item.session_id)"><Icon name="chat" :size="17" /><span>{{ item.title }}</span><span class="search-date">{{ dateLabel(item.updated_at) }}</span><Icon name="chevron" :size="13" /></button><p v-if="!filtered.length" class="empty-state">无匹配会话</p></div><button v-if="hasMore" class="load-more" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button></dialog>

    <dialog ref="editDialog" class="edit-dialog acrylic" aria-labelledby="edit-title"><form @submit.prevent="confirmEdit"><h2 id="edit-title">{{ editKind === 'rename' ? '重命名' : '删除会话？' }}</h2><input v-if="editKind === 'rename'" ref="titleInput" v-model="titleDraft" maxlength="200" required aria-label="会话名称" /><p v-else>会话与消息将被永久删除。</p><div class="dialog-actions"><button class="secondary-button" type="button" :disabled="busy" @click="editDialog.close()">取消</button><button class="primary-button" :class="{ destructive: editKind === 'delete' }" type="submit" :disabled="busy || (editKind === 'rename' && !titleDraft.trim())">{{ busy ? '处理中…' : editKind === 'rename' ? '保存' : '删除' }}</button></div></form></dialog>
  </div>
</template>
