import { computed, reactive, ref } from 'vue'
import { api } from '../api/client.js'

const storageKey = 'rhizome.activeSession'
function remember(id) { try { id ? localStorage.setItem(storageKey, id) : localStorage.removeItem(storageKey) } catch {} }
function previousSession() { try { return localStorage.getItem(storageKey) } catch { return null } }

export function useChat() {
  const sessions = ref([])
  const total = ref(0)
  const activeSession = ref(null)
  const pendingWorkspaceId = ref(null)
  const workspaceId = computed(() => activeSession.value ? activeSession.value.workspace_id ?? null : pendingWorkspaceId.value)
  const messages = ref([])
  const busy = ref(false)
  const streaming = ref(false)
  const loading = ref(false)
  const connected = ref(false)
  const notice = ref('')
  let controller = null
  let noticeTimer
  let navigation = 0

  function notify(text) {
    notice.value = text
    clearTimeout(noticeTimer)
    noticeTimer = setTimeout(() => { notice.value = '' }, 6000)
  }

  async function refreshSessions(append = false) {
    const result = await api.sessions(append ? sessions.value.length : 0)
    sessions.value = append ? [...sessions.value, ...result.items] : result.items
    total.value = result.total
    connected.value = true
  }

  async function refreshAfterChange() {
    try { await refreshSessions() }
    catch { connected.value = false; notify('操作已完成，但会话列表刷新失败，请稍后重新连接') }
  }

  async function openSession(id) {
    if (busy.value) return
    const token = ++navigation
    loading.value = true
    try {
      const [session, history] = await Promise.all([api.session(id), api.messages(id)])
      if (token !== navigation) return
      activeSession.value = session
      pendingWorkspaceId.value = session.workspace_id ?? null
      messages.value = history.messages
      remember(id)
    } catch (error) {
      if (token !== navigation) return
      if (error.status === 404) { activeSession.value = null; messages.value = []; remember(null) }
      notify(error.message)
    } finally { if (token === navigation) loading.value = false }
  }

  async function createSession() {
    if (busy.value || loading.value) return
    busy.value = true
    try {
      const session = await api.create(workspaceId.value)
      activeSession.value = session
      pendingWorkspaceId.value = session.workspace_id ?? null
      messages.value = []
      remember(session.session_id)
      await refreshAfterChange()
      return session
    } catch (error) { notify(error.message) }
    finally { busy.value = false }
  }

  async function selectWorkspace(id) {
    if (busy.value || loading.value) return false
    id = id || null
    if (!activeSession.value) {
      pendingWorkspaceId.value = id
      return true
    }
    if (workspaceId.value === id) return true
    busy.value = true
    try {
      const session = await api.bindWorkspace(activeSession.value.session_id, id)
      activeSession.value = session
      pendingWorkspaceId.value = session.workspace_id ?? null
      sessions.value = sessions.value.map(item => item.session_id === session.session_id ? session : item)
      return true
    } catch (error) { notify(error.message); return false }
    finally { busy.value = false }
  }

  async function renameSession(title) {
    if (busy.value || !activeSession.value) return false
    busy.value = true
    try {
      activeSession.value = await api.rename(activeSession.value.session_id, title)
      pendingWorkspaceId.value = activeSession.value.workspace_id ?? null
      await refreshAfterChange()
      return true
    } catch (error) { notify(error.message); return false }
    finally { busy.value = false }
  }

  async function deleteSession() {
    if (busy.value || !activeSession.value) return false
    busy.value = true
    try {
      await api.remove(activeSession.value.session_id)
      activeSession.value = null
      messages.value = []
      remember(null)
      await refreshAfterChange()
      return true
    } catch (error) { notify(error.message); return false }
    finally { busy.value = false }
  }

  async function sendMessage(text) {
    text = text.trim()
    if (!text || busy.value || loading.value) return false
    busy.value = true
    let assistant
    let submitted = false
    try {
      if (!activeSession.value) {
        activeSession.value = await api.create(workspaceId.value)
        pendingWorkspaceId.value = activeSession.value.workspace_id ?? null
        remember(activeSession.value.session_id)
      }
      const id = activeSession.value.session_id
      messages.value.push({ id: crypto.randomUUID(), role: 'user', content: text })
      submitted = true
      assistant = reactive({ id: crypto.randomUUID(), role: 'assistant', content: '', status: 'streaming' })
      messages.value.push(assistant)
      controller = new AbortController()
      streaming.value = true
      await api.chat(id, text, controller.signal, (event) => {
        if (event.event === 'delta') assistant.content += event.text || ''
        if (event.event === 'done') assistant.status = 'saved'
      })
      const [history, session] = await Promise.all([api.messages(id), api.session(id)])
      messages.value = history.messages
      activeSession.value = session
      pendingWorkspaceId.value = session.workspace_id ?? null
    } catch (error) {
      if (assistant && assistant.status !== 'saved') {
        assistant.status = error.name === 'AbortError' ? 'stopped' : 'error'
      }
      notify(error.name === 'AbortError' ? '已停止接收' : error.message)
    } finally {
      streaming.value = false
      controller = null
      busy.value = false
      try { await refreshSessions() } catch { connected.value = false }
    }
    return submitted
  }

  function resetSession() {
    if (busy.value || loading.value) return
    pendingWorkspaceId.value = workspaceId.value
    activeSession.value = null
    messages.value = []
    remember(null)
  }

  async function initialize() {
    loading.value = true
    try {
      await refreshSessions()
    } catch (error) { connected.value = false; notify('连接失败，请确认服务已启动') }
    finally { loading.value = false }
    const id = previousSession()
    if (id && connected.value) await openSession(id)
  }

  return {
    sessions, total, activeSession, workspaceId, messages, busy, streaming, loading, connected, notice,
    hasMore: computed(() => sessions.value.length < total.value),
    initialize, refreshSessions, openSession, createSession, selectWorkspace, renameSession, deleteSession,
    sendMessage, resetSession, stop: () => controller?.abort(), notify,
  }
}
