import { consumeSSE } from './sse.js'

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status }
}

async function checked(response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const detail = typeof data.detail === 'string' ? data.detail : '请求未能完成，请检查输入后重试'
    throw new ApiError(detail, response.status)
  }
  return response
}

async function request(path, options = {}) {
  const response = await checked(await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  }))
  return response.status === 204 ? null : response.json()
}

const base = '/api/v1/sessions'
const path = (id) => `${base}/${encodeURIComponent(id)}`
const workspaceBase = '/api/v1/workspaces'
const workspacePath = (id) => `${workspaceBase}/${encodeURIComponent(id)}`

export const api = {
  sessions: (offset = 0) => request(`${base}?limit=50&offset=${offset}`),
  create: (workspaceId = null) => request(base, { method: 'POST', body: JSON.stringify({ title: '新会话', workspace_id: workspaceId }) }),
  session: (id) => request(path(id)),
  messages: (id) => request(`${path(id)}/messages`),
  rename: (id, title) => request(path(id), { method: 'PATCH', body: JSON.stringify({ title }) }),
  remove: (id) => request(path(id), { method: 'DELETE' }),
  bindWorkspace: (id, workspaceId) => request(`${path(id)}/workspace`, { method: 'PUT', body: JSON.stringify({ workspace_id: workspaceId }) }),
  workspaces: (offset = 0) => request(`${workspaceBase}?limit=50&offset=${offset}`),
  workspace: (id) => request(workspacePath(id)),
  createWorkspace: (body) => request(workspaceBase, { method: 'POST', body: JSON.stringify(body) }),
  updateWorkspaceSettings: (id, body) => request(`${workspacePath(id)}/settings`, { method: 'PUT', body: JSON.stringify(body) }),
  async chat(id, message, signal, onEvent) {
    const response = await checked(await fetch(`${path(id)}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ message }),
      signal,
    }))
    await consumeSSE(response, onEvent)
  },
}
