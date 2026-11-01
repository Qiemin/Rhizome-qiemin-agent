import { computed, onMounted, onUnmounted, ref } from 'vue'

const STORAGE_KEY = 'rhizome.sidebarWidth'
const MIN_WIDTH = 200
const MAX_WIDTH = 480
const MOBILE_BREAKPOINT = 800

export function useSidebarResize() {
  function savedWidth() {
    try {
      const value = Number(localStorage.getItem(STORAGE_KEY))
      return Number.isFinite(value) && value >= MIN_WIDTH ? Math.min(value, MAX_WIDTH) : MIN_WIDTH
    } catch { return MIN_WIDTH }
  }

  const preferredWidth = ref(savedWidth())
  const viewportWidth = ref(window.innerWidth)
  const resizingSidebar = ref(false)
  const sidebarMaxWidth = computed(() => Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, viewportWidth.value - 480)))
  const sidebarWidth = computed(() => Math.max(MIN_WIDTH, Math.min(sidebarMaxWidth.value, preferredWidth.value)))
  let drag = null

  function rememberWidth() {
    try { localStorage.setItem(STORAGE_KEY, String(preferredWidth.value)) } catch {}
  }

  function setWidth(value) {
    preferredWidth.value = Math.round(Math.max(MIN_WIDTH, Math.min(sidebarMaxWidth.value, value)))
  }

  function startSidebarResize(event) {
    if (viewportWidth.value <= MOBILE_BREAKPOINT || event.button !== 0 || !event.isPrimary) return
    event.preventDefault()
    event.currentTarget.focus({ preventScroll: true })
    drag = { pointerId: event.pointerId, startX: event.clientX, startWidth: sidebarWidth.value, handle: event.currentTarget }
    event.currentTarget.setPointerCapture(event.pointerId)
    resizingSidebar.value = true
  }

  function moveSidebarResize(event) {
    if (!drag || event.pointerId !== drag.pointerId) return
    setWidth(drag.startWidth + event.clientX - drag.startX)
  }

  function stopSidebarResize(event) {
    if (!drag || (event?.pointerId != null && event.pointerId !== drag.pointerId)) return
    const finished = drag
    drag = null
    resizingSidebar.value = false
    if (finished.handle.hasPointerCapture(finished.pointerId)) finished.handle.releasePointerCapture(finished.pointerId)
    rememberWidth()
  }

  function resizeSidebarWithKeyboard(event) {
    const step = event.shiftKey ? 30 : 10
    const widths = { ArrowLeft: sidebarWidth.value - step, ArrowRight: sidebarWidth.value + step, Home: MIN_WIDTH, End: sidebarMaxWidth.value }
    if (!(event.key in widths)) return
    event.preventDefault()
    setWidth(widths[event.key])
    rememberWidth()
  }

  function resizeViewport() {
    viewportWidth.value = window.innerWidth
    if (viewportWidth.value <= MOBILE_BREAKPOINT) stopSidebarResize()
  }

  onMounted(() => {
    window.addEventListener('resize', resizeViewport)
    window.addEventListener('blur', stopSidebarResize)
  })
  onUnmounted(() => {
    stopSidebarResize()
    window.removeEventListener('resize', resizeViewport)
    window.removeEventListener('blur', stopSidebarResize)
  })

  return { sidebarWidth, sidebarMinWidth: MIN_WIDTH, sidebarMaxWidth, resizingSidebar, startSidebarResize, moveSidebarResize, stopSidebarResize, resizeSidebarWithKeyboard }
}
