import test from 'node:test'
import assert from 'node:assert/strict'
import { consumeSSE, parseSSEFrame } from '../src/api/sse.js'

function response(text, stride = 1) {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream({
    start(controller) {
      for (let i = 0; i < bytes.length; i += stride) controller.enqueue(bytes.slice(i, i + stride))
      controller.close()
    },
  }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

test('SSE survives UTF-8 bytes, split CRLF, newlines and empty keepalive frames', async () => {
  const text = ': keepalive\r\n\r\nevent: delta\r\ndata: {"text":"你好\\n世界"}\r\n\r\nevent: done\r\ndata: {"session_id":"demo"}\r\n\r\n'
  const events = []
  await consumeSSE(response(text), event => events.push(event))
  assert.deepEqual(events, [{ event: 'delta', text: '你好\n世界' }, { event: 'done', session_id: 'demo' }])
})

test('a server error cannot be treated as a successful reply', async () => {
  await assert.rejects(consumeSSE(response('event: error\ndata: {"message":"保存失败"}\n\n'), () => {}), /保存失败/)
})

test('a disconnected stream requires the persistence done event', async () => {
  await assert.rejects(consumeSSE(response('event: delta\ndata: {"text":"partial"}\n\n'), () => {}), /连接提前结束/)
})

test('invalid JSON is rejected and comments are ignored', () => {
  assert.equal(parseSSEFrame(': hello'), null)
  assert.throws(() => parseSSEFrame('data: invalid'), SyntaxError)
})
