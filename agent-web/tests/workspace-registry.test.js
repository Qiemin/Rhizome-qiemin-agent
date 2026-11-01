import test from 'node:test'
import assert from 'node:assert/strict'
import { api } from '../src/api/client.js'
import { useWorkspaces } from '../src/composables/useWorkspaces.js'

const workspace = id => ({ workspace_id: id, name: id, root_path: `D:\\${id}`, writable: false, execution_mode: 'disabled' })
function replaceApi(values) {
  const original = Object.fromEntries(Object.keys(values).map(key => [key, api[key]]))
  Object.assign(api, values)
  return () => Object.assign(api, original)
}

test('resolving an off-page selected workspace does not skip any list page', async () => {
  const offsets = []
  const restore = replaceApi({
    workspaces: async offset => { offsets.push(offset); return offset === 0 ? { items: [workspace('a'), workspace('b')], total: 3 } : { items: [workspace('c')], total: 3 } },
    workspace: async id => workspace(id),
  })
  try {
    const store = useWorkspaces()
    await store.refresh()
    await store.resolve('c')
    assert.equal(store.get('c').name, 'c')
    assert.equal(store.items.value.length, 2)
    await store.refresh(true)
    assert.deepEqual(offsets, [0, 2])
    assert.deepEqual(store.items.value.map(item => item.workspace_id), ['a', 'b', 'c'])
    assert.equal(store.hasMore.value, false)
  } finally { restore() }
})

test('a completed create survives list refresh failure and is not sent twice', async () => {
  let posts = 0
  const restore = replaceApi({
    createWorkspace: async body => { posts++; return { ...body, workspace_id: 'new' } },
    workspaces: async () => { throw new Error('列表刷新失败') },
  })
  try {
    const store = useWorkspaces()
    const result = await store.save({ name: '办公资料', root_path: 'D:\\资料', writable: false, execution_mode: 'disabled' })
    assert.equal(posts, 1)
    assert.equal(result.workspace_id, 'new')
    assert.equal(store.items.value[0].workspace_id, 'new')
    assert.equal(store.error.value, '列表刷新失败')
    assert.equal(store.saving.value, false)
  } finally { restore() }
})

test('settings update refreshes cached selected details and propagates rejected saves', async () => {
  let saved = workspace('docs')
  const restore = replaceApi({
    workspace: async () => saved,
    workspaces: async () => ({ items: [saved], total: 1 }),
    updateWorkspaceSettings: async (id, body) => { saved = { ...saved, ...body }; return saved },
  })
  try {
    const store = useWorkspaces()
    await store.resolve('docs')
    await store.refresh()
    await store.save({ name: '已更名', writable: true, execution_mode: 'local' }, 'docs')
    assert.equal(store.get('docs').execution_mode, 'local')
    assert.equal(store.items.value[0].name, '已更名')
    api.updateWorkspaceSettings = async () => { throw new Error('工作区正在执行命令') }
    await assert.rejects(() => store.save({ name: '不会保存' }, 'docs'), /工作区正在执行命令/)
    assert.equal(store.get('docs').name, '已更名')
    assert.equal(store.saving.value, false)
  } finally { restore() }
})
