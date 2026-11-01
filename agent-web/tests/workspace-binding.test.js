import test from 'node:test'
import assert from 'node:assert/strict'
import { api, ApiError } from '../src/api/client.js'
import { useChat } from '../src/composables/useChat.js'

function replaceApi(values) {
  const original = Object.fromEntries(Object.keys(values).map(key => [key, api[key]]))
  Object.assign(api, values)
  return () => Object.assign(api, original)
}
const list = { items: [], total: 0 }

test('choosing before creation persists the workspace when creating a session', async () => {
  const calls = []
  const restore = replaceApi({
    create: async id => { calls.push(id); return { session_id: 'new', workspace_id: id } },
    sessions: async () => list,
    bindWorkspace: async () => assert.fail('a nonexistent session cannot be bound'),
  })
  try {
    const chat = useChat()
    assert.equal(await chat.selectWorkspace('docs'), true)
    assert.equal(chat.activeSession.value, null)
    await chat.createSession()
    assert.deepEqual(calls, ['docs'])
    assert.equal(chat.workspaceId.value, 'docs')
  } finally { restore() }
})

test('the implicit session for a first message also includes the selected workspace', async () => {
  let createdWith
  const session = { session_id: 'first', workspace_id: 'docs' }
  const restore = replaceApi({
    create: async id => { createdWith = id; return session },
    chat: async (id, message, signal, onEvent) => { onEvent({ event: 'delta', text: '已完成' }); onEvent({ event: 'done' }) },
    messages: async () => ({ messages: [{ id: 'reply', role: 'assistant', content: '已完成' }] }),
    session: async () => session,
    sessions: async () => list,
  })
  try {
    const chat = useChat()
    await chat.selectWorkspace('docs')
    assert.equal(await chat.sendMessage('读取资料'), true)
    assert.equal(createdWith, 'docs')
    assert.equal(chat.messages.value[0].content, '已完成')
    assert.equal(chat.busy.value, false)
  } finally { restore() }
})

test('binding waits for the server, updates the list, and can be explicitly removed', async () => {
  const calls = []
  let release
  const restore = replaceApi({ bindWorkspace: (sessionId, workspaceId) => {
    calls.push([sessionId, workspaceId])
    return new Promise(resolve => { release = () => resolve({ session_id: sessionId, workspace_id: workspaceId, title: '当前会话' }) })
  } })
  try {
    const chat = useChat()
    chat.activeSession.value = { session_id: 'saved', workspace_id: 'old' }
    chat.sessions.value = [chat.activeSession.value]
    let pending = chat.selectWorkspace('new')
    assert.equal(chat.workspaceId.value, 'old')
    assert.equal(chat.busy.value, true)
    assert.equal(await chat.selectWorkspace('another'), false)
    release()
    assert.equal(await pending, true)
    assert.equal(chat.workspaceId.value, 'new')
    assert.equal(chat.sessions.value[0].workspace_id, 'new')
    pending = chat.selectWorkspace(null)
    release()
    assert.equal(await pending, true)
    assert.equal(chat.workspaceId.value, null)
    assert.deepEqual(calls, [['saved', 'new'], ['saved', null]])
  } finally { restore() }
})

test('a rejected binding preserves the server-confirmed workspace and messages', async () => {
  const restore = replaceApi({ bindWorkspace: async () => { throw new ApiError('会话正在处理请求', 409) } })
  try {
    const chat = useChat()
    chat.activeSession.value = { session_id: 'saved', workspace_id: 'old' }
    chat.messages.value = [{ id: 'message', content: 'history' }]
    assert.equal(await chat.selectWorkspace(null), false)
    assert.equal(chat.workspaceId.value, 'old')
    assert.equal(chat.messages.value[0].content, 'history')
    assert.equal(chat.notice.value, '会话正在处理请求')
    assert.equal(chat.busy.value, false)
  } finally { restore() }
})

test('switching sessions restores each persisted binding and plain chat stays unbound', async () => {
  const restore = replaceApi({
    session: async id => ({ session_id: id, workspace_id: id === 'bound' ? 'docs' : null }),
    messages: async () => ({ messages: [] }),
  })
  try {
    const chat = useChat()
    await chat.openSession('bound')
    assert.equal(chat.workspaceId.value, 'docs')
    chat.resetSession()
    assert.equal(chat.workspaceId.value, 'docs')
    await chat.openSession('plain')
    assert.equal(chat.workspaceId.value, null)
    chat.loading.value = true
    assert.equal(await chat.selectWorkspace('blocked'), false)
    assert.equal(chat.workspaceId.value, null)
  } finally { restore() }
})

test('a browser refresh restores the workspace from the remembered session, not browser workspace data', async () => {
  const storage = globalThis.localStorage
  globalThis.localStorage = { getItem: key => key === 'rhizome.activeSession' ? 'saved' : null, setItem() {}, removeItem() {} }
  const restore = replaceApi({
    sessions: async () => list,
    session: async id => ({ session_id: id, workspace_id: 'persisted' }),
    messages: async () => ({ messages: [] }),
  })
  try {
    const chat = useChat()
    await chat.initialize()
    assert.equal(chat.workspaceId.value, 'persisted')
  } finally {
    restore()
    if (storage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = storage
  }
})
