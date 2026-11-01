import copy
import asyncio
from threading import Event
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from psycopg import OperationalError

from agent.api.app import create_app
from agent.api.dependencies import get_database_url, get_graph
from agent.api.routers import sessions as routes
from agent.api.routers import chat as chat_routes
from agent.api.schemas.chat import ChatRequest
from agent.services import chat
from agent.services.locking import SessionBusyError, session_guard
from agent.storage import sessions as store


class MemoryStore:
    """An isolated test double; never used by the running application."""

    def __init__(self):
        self.sessions = {}
        self.messages = {}

    def create(self, database_url, title='新会话', workspace_id=None):
        now = datetime.now(timezone.utc)
        session = dict(session_id=str(uuid4()), title=title, created_at=now, updated_at=now, message_count=0)
        session['workspace_id'] = workspace_id
        self.sessions[session['session_id']] = session
        return copy.deepcopy(session)

    def get(self, database_url, session_id):
        value = self.sessions.get(session_id)
        return copy.deepcopy(value)

    def list(self, database_url, limit=50, offset=0):
        values = sorted(self.sessions.values(), key=lambda row: (row['updated_at'], row['session_id']), reverse=True)
        return dict(items=copy.deepcopy(values[offset:offset + limit]), total=len(values), limit=limit, offset=offset)

    def rename(self, database_url, session_id, title):
        if session_id not in self.sessions:
            raise store.SessionNotFoundError(session_id)
        self.sessions[session_id]['title'] = title
        return self.get(database_url, session_id)

    def delete(self, database_url, session_id):
        if self.sessions.pop(session_id, None) is None:
            raise store.SessionNotFoundError(session_id)
        self.messages.pop(session_id, None)

    def load(self, database_url, session_id):
        return copy.deepcopy(self.messages.get(session_id, []))

    def save(self, database_url, session_id, messages):
        if session_id not in self.sessions:
            raise store.SessionNotFoundError(session_id)
        self.messages[session_id] = copy.deepcopy(messages)
        self.sessions[session_id]['message_count'] = len(messages)


class StreamingGraph:
    def __init__(self):
        self.inputs = []
        self.failure = False
        self.closed = 0

    def stream(self, state, **kwargs):
        self.inputs.append(copy.deepcopy(state))
        try:
            history = state['messages']
            yield {'type': 'values', 'data': {'messages': history}}
            yield {'type': 'messages', 'data': (AIMessageChunk(content='hidden'), {'langgraph_node': 'internal'})}
            yield {'type': 'messages', 'data': (AIMessageChunk(content='你好\n'), {'langgraph_node': 'chat'})}
            if self.failure:
                raise RuntimeError('upstream-private-detail')
            if history[-1].content == 'tools':
                history = [*history, AIMessage(content='', tool_calls=[{'name': 'multiply', 'args': {'a': 2, 'b': 3}, 'id': 'tool-1', 'type': 'tool_call'}]), ToolMessage(content='6', tool_call_id='tool-1', name='multiply')]
            yield {'type': 'messages', 'data': (AIMessageChunk(content='世界'), {'langgraph_node': 'chat'})}
            yield {'type': 'values', 'data': {'messages': [*history, AIMessage(content='你好\n世界')]}}
        finally:
            self.closed += 1


def install_memory(stack, memory):
    for name, replacement in (
        ('create_session', memory.create), ('get_session', memory.get),
        ('list_sessions', memory.list), ('rename_session', memory.rename),
        ('delete_session', memory.delete),
    ):
        stack.enter_context(patch.object(store, name, side_effect=replacement))
    stack.enter_context(patch.object(routes, 'load_messages', side_effect=memory.load))
    stack.enter_context(patch.object(chat, 'load_messages', side_effect=memory.load))
    stack.enter_context(patch.object(chat, 'save_messages', side_effect=memory.save))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.memory = MemoryStore()
        self.graph = StreamingGraph()
        install_memory(self.stack, self.memory)
        app = create_app()
        app.dependency_overrides[get_database_url] = lambda: 'offline'
        app.dependency_overrides[get_graph] = lambda: self.graph
        # No context manager: lifespan must not load local .env or create a real model.
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def create(self, title='新会话'):
        response = self.client.post('/api/v1/sessions', json={'title': title})
        self.assertEqual(response.status_code, 201)
        return response.json()['session_id']

    def test_session_crud_pagination_and_missing(self):
        session_id = self.create()
        base = f'/api/v1/sessions/{session_id}'
        self.assertEqual(self.client.get('/api/v1/sessions').json()['total'], 1)
        self.assertEqual(self.client.get('/api/v1/sessions?limit=1&offset=1').json()['items'], [])
        self.assertEqual(self.client.get(base).json()['message_count'], 0)
        self.assertEqual(self.client.get(base + '/messages').json()['messages'], [])
        renamed = self.client.patch(base, json={'title': '  工作计划  '})
        self.assertEqual(renamed.json()['title'], '工作计划')
        self.assertEqual(self.client.delete(base).status_code, 204)
        self.assertEqual(self.client.get(base).status_code, 404)
        self.assertEqual(self.client.post(base + '/messages', json={'message': 'hello'}).status_code, 404)
        self.assertEqual(self.graph.inputs, [])

    def test_validation_precedes_model_calls(self):
        session_id = self.create()
        for message in ('', '   ', 'x' * 32001):
            result = self.client.post(f'/api/v1/sessions/{session_id}/messages', json={'message': message})
            self.assertEqual(result.status_code, 422)
        self.assertEqual(self.client.post('/api/v1/sessions', json={'title': '  '}).status_code, 422)
        self.assertEqual(self.client.get('/api/v1/sessions?limit=0').status_code, 422)
        self.assertEqual(self.graph.inputs, [])

    def test_streaming_persists_tool_history_and_restores_next_turn(self):
        session_id = self.create()
        url = f'/api/v1/sessions/{session_id}/messages'
        response = self.client.post(url, json={'message': 'tools'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/event-stream', response.headers['content-type'])
        self.assertIn('event: delta', response.text)
        self.assertIn('event: done', response.text)
        self.assertNotIn('hidden', response.text)
        history = self.client.get(url).json()['messages']
        self.assertEqual([row['role'] for row in history], ['user', 'assistant', 'tool', 'assistant'])
        self.assertEqual(history[2]['content'], '6')
        self.assertEqual(history[1]['tool_calls'][0]['id'], 'tool-1')
        self.client.post(url, json={'message': 'continue'})
        self.assertEqual(len(self.graph.inputs[-1]['messages']), 5)
        self.assertEqual(self.client.get('/api/v1/sessions').json()['items'][0]['message_count'], 6)

    def test_failure_does_not_emit_done_or_overwrite_saved_history(self):
        session_id = self.create()
        url = f'/api/v1/sessions/{session_id}/messages'
        self.client.post(url, json={'message': 'first'})
        saved = copy.deepcopy(self.memory.messages[session_id])
        self.graph.failure = True
        response = self.client.post(url, json={'message': 'failed'})
        self.assertIn('event: error', response.text)
        self.assertNotIn('event: done', response.text)
        self.assertNotIn('upstream-private-detail', response.text)
        self.assertEqual(self.memory.messages[session_id], saved)
        self.graph.failure = False
        with patch.object(chat, 'save_messages', side_effect=OperationalError('private-database-url')):
            response = self.client.post(url, json={'message': 'unsaved'})
        self.assertIn('event: error', response.text)
        self.assertNotIn('event: done', response.text)
        self.assertNotIn('private-database-url', response.text)

    def test_busy_session_cannot_be_deleted_or_renamed(self):
        session_id = self.create()
        url = f'/api/v1/sessions/{session_id}'
        with session_guard(session_id):
            self.assertEqual(self.client.delete(url).status_code, 409)
            self.assertEqual(self.client.patch(url, json={'title': 'changed'}).status_code, 409)
            self.assertIn('event: error', self.client.post(url + '/messages', json={'message': 'blocked'}).text)
        self.assertEqual(self.client.get(url).json()['title'], '新会话')

    def test_closing_generator_releases_session_without_partial_save(self):
        session_id = self.create()
        stream = chat.stream_turn(self.graph, 'offline', session_id, 'hello')
        self.assertEqual(next(stream)['event'], 'delta')
        with self.assertRaises(SessionBusyError):
            with session_guard(session_id):
                pass
        stream.close()
        self.assertEqual(self.graph.closed, 1)
        self.assertNotIn(session_id, self.memory.messages)
        with session_guard(session_id):
            pass

    def test_removed_health_and_unknown_api_are_not_served(self):
        self.assertEqual(self.client.get('/health').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/unknown').status_code, 404)

    def test_stream_cleanup_does_not_block_the_event_loop(self):
        session_id = self.create()
        release = Event()
        blocked = []

        def slow_stream(**kwargs):
            try:
                yield {'event': 'delta', 'text': 'partial'}
            finally:
                if not release.wait(timeout=0.5):
                    blocked.append(True)

        async def exercise():
            response = chat_routes.send_message(
                session_id, ChatRequest(message='hello'), self.graph, 'offline',
            )
            iterator = response.body_iterator
            await anext(iterator)

            async def another_request_can_progress():
                await asyncio.sleep(0.01)
                release.set()

            other = asyncio.create_task(another_request_can_progress())
            await iterator.aclose()
            await other

        with patch.object(chat_routes, 'stream_turn', side_effect=slow_stream):
            asyncio.run(exercise())
        self.assertEqual(blocked, [])


if __name__ == '__main__':
    unittest.main()
