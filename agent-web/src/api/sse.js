export function parseSSEFrame(frame) {
  let eventName = 'message'
  const data = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim()
    if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
  }
  if (!data.length) return null
  const payload = JSON.parse(data.join('\n'))
  return { ...payload, event: eventName === 'message' ? payload.event : eventName }
}

export async function consumeSSE(response, onEvent) {
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('服务没有返回有效的流式回复')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  let ended = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const event = parseSSEFrame(frame)
        if (!event) continue
        if (event.event === 'error') throw new Error(event.message || '回复执行失败')
        if (event.event === 'done') completed = true
        onEvent(event)
      }
      if (done) { ended = true; break }
    }
    if (!completed) throw new Error('连接提前结束，请重新打开会话确认回复状态')
  } finally {
    if (!ended) await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
