import test from 'node:test'
import assert from 'node:assert/strict'
import { useChat } from '../src/composables/useChat.js'
import { api } from '../src/api/client.js'

test('workspace initializes from the session API without a health endpoint', async () => {
  const original = api.sessions
  api.sessions = async () => ({ items: [], total: 0, limit: 50, offset: 0 })
  try {
    const workspace = useChat()
    await workspace.initialize()
    assert.equal(workspace.connected.value, true)
    assert.equal(workspace.loading.value, false)
    assert.equal(workspace.total.value, 0)
  } finally {
    api.sessions = original
  }
})

test('returning to workbench clears only the selected conversation', () => {
  const workspace = useChat()
  workspace.sessions.value = [{ session_id: 'saved', title: 'Saved session' }]
  workspace.activeSession.value = workspace.sessions.value[0]
  workspace.messages.value = [{ id: 'message', content: 'saved content' }]
  workspace.resetSession()
  assert.equal(workspace.activeSession.value, null)
  assert.deepEqual(workspace.messages.value, [])
  assert.equal(workspace.sessions.value.length, 1)
})

test('returning to workbench cannot discard a currently streaming conversation', () => {
  const workspace = useChat()
  workspace.activeSession.value = { session_id: 'running' }
  workspace.busy.value = true
  workspace.resetSession()
  assert.equal(workspace.activeSession.value.session_id, 'running')
})
