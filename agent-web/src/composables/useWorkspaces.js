import { computed, ref } from 'vue'
import { api } from '../api/client.js'

export function useWorkspaces() {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const saving = ref(false)
  const loaded = ref(false)
  const error = ref('')
  const records = ref(new Map())
  const nextOffset = ref(0)

  function cache(item) {
    records.value.set(item.workspace_id, item)
    return item
  }

  async function refresh(append = false) {
    if (loading.value) return false
    loading.value = true
    error.value = ''
    try {
      const offset = append ? nextOffset.value : 0
      const result = await api.workspaces(offset)
      result.items.forEach(cache)
      const combined = append ? [...items.value, ...result.items] : result.items
      items.value = [...new Map(combined.map(item => [item.workspace_id, item])).values()]
      nextOffset.value = offset + result.items.length
      total.value = result.total
      loaded.value = true
      return true
    } catch (failure) { error.value = failure.message; return false }
    finally { loading.value = false }
  }

  async function resolve(id) {
    return id ? cache(await api.workspace(id)) : null
  }

  async function save(body, id = null) {
    if (saving.value || loading.value) return null
    saving.value = true
    try {
      const item = cache(id ? await api.updateWorkspaceSettings(id, body) : await api.createWorkspace(body))
      const index = items.value.findIndex(existing => existing.workspace_id === item.workspace_id)
      if (index !== -1) items.value[index] = item
      else {
        items.value.unshift(item)
        total.value += 1
        nextOffset.value += 1
      }
      // A refresh failure must not turn a completed save into a duplicate POST.
      await refresh()
      return item
    } finally { saving.value = false }
  }

  return {
    items, total, loading, saving, loaded, error,
    hasMore: computed(() => nextOffset.value < total.value),
    get: id => records.value.get(id) || null,
    refresh, resolve, save,
  }
}
