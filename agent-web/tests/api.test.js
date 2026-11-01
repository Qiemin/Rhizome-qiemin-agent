import test from 'node:test'
import assert from 'node:assert/strict'
import { api, ApiError } from '../src/api/client.js'

test('workspace requests follow the backend contract, including explicit unbinding', async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, method: options.method || 'GET', body: options.body && JSON.parse(options.body) })
    return Response.json({ workspace_id: 'workspace' })
  }
  const settings = { name: '办公资料', writable: true, execution_mode: 'local' }
  const body = { ...settings, root_path: 'D:\\办公资料' }
  try {
    await api.workspaces(50)
    await api.workspace('space/id')
    await api.createWorkspace(body)
    await api.updateWorkspaceSettings('space/id', settings)
    await api.create('workspace')
    await api.bindWorkspace('session/id', 'workspace')
    await api.bindWorkspace('session/id', null)
    await api.create()
    assert.deepEqual(calls, [
      { url: '/api/v1/workspaces?limit=50&offset=50', method: 'GET', body: undefined },
      { url: '/api/v1/workspaces/space%2Fid', method: 'GET', body: undefined },
      { url: '/api/v1/workspaces', method: 'POST', body },
      { url: '/api/v1/workspaces/space%2Fid/settings', method: 'PUT', body: settings },
      { url: '/api/v1/sessions', method: 'POST', body: { title: '新会话', workspace_id: 'workspace' } },
      { url: '/api/v1/sessions/session%2Fid/workspace', method: 'PUT', body: { workspace_id: 'workspace' } },
      { url: '/api/v1/sessions/session%2Fid/workspace', method: 'PUT', body: { workspace_id: null } },
      { url: '/api/v1/sessions', method: 'POST', body: { title: '新会话', workspace_id: null } },
    ])
  } finally { globalThis.fetch = original }
})

test('workspace conflicts and bad paths keep their HTTP status and server message', async () => {
  const original = globalThis.fetch
  try {
    for (const [status, detail] of [[409, '工作区正在执行命令，请稍后修改设置'], [422, '工作区必须是存在且可访问的绝对目录路径']]) {
      globalThis.fetch = async () => Response.json({ detail }, { status })
      await assert.rejects(() => api.createWorkspace({}), error => error instanceof ApiError && error.status === status && error.message === detail)
    }
  } finally { globalThis.fetch = original }
})
