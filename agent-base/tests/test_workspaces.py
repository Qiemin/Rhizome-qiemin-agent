import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import ToolException

from agent.api.app import create_app
from agent.api.dependencies import get_database_url, get_graph
from agent.execution.models import CommandResult
from agent.graph import builder
from agent.storage import sessions, workspaces
from agent.storage.storage import init_db
from agent.tools.terminal import build_terminal_tool
from agent.workspace.workspace import open_workspace
from test_api import MemoryStore, StreamingGraph, install_memory


class WorkspaceMemory(MemoryStore):
    def __init__(self):
        super().__init__()
        self.workspaces = {}

    def create_workspace(self, database_url, name, root_path, writable=False, execution_mode='disabled'):
        value = open_workspace(root_path, writable=writable, execution_mode=execution_mode)
        if any(row['root_path'] == str(value.root) for row in self.workspaces.values()):
            raise workspaces.WorkspaceConflictError('duplicate')
        row = dict(workspace_id=str(uuid4()), name=name, root_path=str(value.root),
                   writable=writable, execution_mode=execution_mode, created_at=datetime.now(timezone.utc))
        self.workspaces[row['workspace_id']] = row
        return copy.deepcopy(row)

    def require_workspace(self, database_url, workspace_id):
        if workspace_id not in self.workspaces:
            raise workspaces.WorkspaceNotFoundError(workspace_id)
        return copy.deepcopy(self.workspaces[workspace_id])

    def list_workspaces(self, database_url, limit=50, offset=0):
        rows = list(self.workspaces.values())
        return dict(items=copy.deepcopy(rows[offset:offset + limit]), total=len(rows), limit=limit, offset=offset)

    def update_settings(self, database_url, workspace_id, name, writable=False, execution_mode='disabled'):
        row = self.require_workspace(database_url, workspace_id)
        open_workspace(row['root_path'], writable=writable, execution_mode=execution_mode)
        row.update(name=name, writable=writable, execution_mode=execution_mode)
        self.workspaces[workspace_id] = row
        return copy.deepcopy(row)

    def create(self, database_url, title='新会话', workspace_id=None):
        if workspace_id is not None:
            self.require_workspace(database_url, workspace_id)
        return super().create(database_url, title, workspace_id)

    def bind(self, database_url, session_id, workspace_id):
        if session_id not in self.sessions:
            raise sessions.SessionNotFoundError(session_id)
        if workspace_id is not None:
            self.require_workspace(database_url, workspace_id)
        self.sessions[session_id]['workspace_id'] = workspace_id
        return self.get(database_url, session_id)


class WorkspaceApiTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.memory = WorkspaceMemory()
        self.graph = StreamingGraph()
        install_memory(self.stack, self.memory)
        for name, replacement in (
            ('create_workspace', self.memory.create_workspace),
            ('list_workspaces', self.memory.list_workspaces),
            ('require_workspace', self.memory.require_workspace),
            ('update_settings', self.memory.update_settings),
        ):
            self.stack.enter_context(patch.object(workspaces, name, side_effect=replacement))
        self.stack.enter_context(patch.object(sessions, 'bind_workspace', side_effect=self.memory.bind))
        self.client = self.new_client()

    def new_client(self, graph=None):
        application = create_app()
        application.dependency_overrides[get_database_url] = lambda: 'offline'
        application.dependency_overrides[get_graph] = lambda: graph or self.graph
        client = TestClient(application)  # lifespan deliberately not entered
        self.addCleanup(client.close)
        return client

    def register(self, **changes):
        body = dict(name='测试工作区', root_path=self.directory, writable=True, execution_mode='local')
        body.update(changes)
        response = self.client.post('/api/v1/workspaces', json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_registration_and_session_binding_survive_app_recreation(self):
        row = self.register()
        sid = self.client.post('/api/v1/sessions', json={'workspace_id': row['workspace_id']}).json()['session_id']
        # Same database double, a new application instance: no in-process global
        # workspace selection is required. Real PostgreSQL restart is manual QA.
        other_client = self.new_client()
        self.assertEqual(other_client.get('/api/v1/workspaces').json()['total'], 1)
        saved = other_client.get(f'/api/v1/sessions/{sid}').json()
        self.assertEqual(saved['workspace_id'], row['workspace_id'])
        restored = workspaces.restore_workspace('offline', saved['workspace_id'])
        self.assertEqual(restored.root, Path(self.directory).resolve())
        self.assertEqual(restored.execution_mode, 'local')

    def test_bind_unbind_and_busy_session(self):
        row = self.register()
        sid = self.client.post('/api/v1/sessions', json={}).json()['session_id']
        url = f'/api/v1/sessions/{sid}/workspace'
        self.assertEqual(self.client.put(url, json={'workspace_id': row['workspace_id']}).json()['workspace_id'], row['workspace_id'])
        self.assertIsNone(self.client.put(url, json={'workspace_id': None}).json()['workspace_id'])
        from agent.services.locking import session_guard
        with session_guard(sid):
            self.assertEqual(self.client.put(url, json={'workspace_id': row['workspace_id']}).status_code, 409)
        self.assertEqual(self.client.put(url, json={'workspace_id': 'missing'}).status_code, 404)

    def test_invalid_root_duplicate_and_readonly_execution(self):
        for root in ('.', str(Path(self.directory) / 'missing')):
            response = self.client.post('/api/v1/workspaces', json={'name': 'test', 'root_path': root})
            self.assertEqual(response.status_code, 422)
        self.register()
        self.assertEqual(self.client.post('/api/v1/workspaces', json={'name': 'again', 'root_path': self.directory}).status_code, 409)
        self.assertEqual(self.client.post('/api/v1/workspaces', json={
            'name': 'test', 'root_path': self.directory, 'execution_mode': 'local',
        }).status_code, 422)

    def test_saved_settings_can_change_and_busy_workspace_is_protected(self):
        row = self.register(execution_mode='disabled', writable=False)
        url = f"/api/v1/workspaces/{row['workspace_id']}/settings"
        response = self.client.put(url, json={'name': '启用终端', 'writable': True, 'execution_mode': 'local'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(f"/api/v1/workspaces/{row['workspace_id']}").json()['execution_mode'], 'local')
        from agent.services.locking import session_guard
        with session_guard('workspace:' + row['workspace_id']):
            self.assertEqual(self.client.put(url, json={'name': '停止终端'}).status_code, 409)
        response = self.client.put(url, json={'name': '停止终端', 'writable': False, 'execution_mode': 'disabled'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['writable'])

    def test_chat_graph_tool_receives_database_selected_workspace(self):
        received = []

        def execute(command, workspace):
            received.append((command, workspace))
            return CommandResult(command, str(workspace.root), 0, 'offline terminal output', '')

        tool = build_terminal_tool(execute)

        class Model:
            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                if isinstance(messages[-1], ToolMessage):
                    assert 'offline terminal output' in messages[-1].content
                    return AIMessage(content='完成')
                return AIMessage(content='', tool_calls=[dict(
                    name='run_terminal', args={'command': "Write-Output 'offline'"}, id='terminal-1', type='tool_call',
                )])

        with patch.object(builder, 'TOOLS', [tool]):
            graph = builder.build_graph(Model())
        row = self.register()
        sid = self.client.post('/api/v1/sessions', json={'workspace_id': row['workspace_id']}).json()['session_id']
        client = self.new_client(graph)
        response = client.post(f'/api/v1/sessions/{sid}/messages', json={'message': '执行测试'})
        self.assertIn('event: done', response.text)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][1].workspace_id, row['workspace_id'])
        history = self.memory.load('offline', sid)
        self.assertEqual([message.type for message in history], ['human', 'ai', 'tool', 'ai'])
        self.assertNotIn('config', tool.args)
        self.assertNotIn('workspace', tool.args)


class WorkspaceStorageTests(unittest.TestCase):
    def test_settings_are_written_to_the_registered_workspace(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(workspaces.psycopg, 'connect') as connect:
            connection = connect.return_value.__enter__.return_value
            old = {'workspace_id': 'w', 'root_path': directory, 'writable': False, 'execution_mode': 'disabled'}
            changed = {**old, 'name': 'new', 'writable': True, 'execution_mode': 'local'}
            connection.execute.return_value.fetchone.side_effect = [old, changed]
            result = workspaces.update_settings('offline', 'w', 'new', True, 'local')
            self.assertEqual(result['execution_mode'], 'local')
            self.assertEqual(connection.execute.call_args.args[1], ('new', True, 'local', 'w'))

    def test_registration_normalizes_path_and_uses_bound_sql_parameters(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(workspaces.psycopg, 'connect') as connect:
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.fetchone.return_value = {'workspace_id': 'saved'}
            row = workspaces.create_workspace('offline', '名称', directory, True, 'local')
            self.assertEqual(row['workspace_id'], 'saved')
            sql, parameters = connection.execute.call_args.args
            self.assertIn('VALUES (%s, %s, %s, %s, %s)', sql)
            self.assertEqual(parameters[2], str(Path(directory).resolve()))
            self.assertEqual(parameters[3:], (True, 'local'))

    def test_session_binding_is_persisted_and_rejects_missing_workspace(self):
        with patch.object(sessions.psycopg, 'connect') as connect:
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.fetchone.side_effect = [
                {'workspace_id': 'w'}, {'session_id': 's', 'workspace_id': 'w'}, {'count': 2},
            ]
            result = sessions.bind_workspace('offline', 's', 'w')
            self.assertEqual(result['workspace_id'], 'w')
            self.assertEqual(result['message_count'], 2)
            self.assertEqual(connection.execute.call_args_list[1].args[1], ('w', 's'))
        with patch.object(sessions.psycopg, 'connect') as connect:
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.fetchone.return_value = None
            with self.assertRaises(workspaces.WorkspaceNotFoundError):
                sessions.bind_workspace('offline', 's', 'missing')

    def test_initialization_extends_schema_without_dropping_history(self):
        with patch('agent.storage.storage.psycopg.connect') as connect:
            init_db('offline')
            connection = connect.return_value.__enter__.return_value
            sql = '\n'.join(call.args[0] for call in connection.execute.call_args_list)
            self.assertIn('CREATE TABLE IF NOT EXISTS workspaces', sql)
            self.assertIn('ADD COLUMN IF NOT EXISTS workspace_id', sql)
            self.assertIn('REFERENCES workspaces (workspace_id)', sql)
            self.assertNotIn('DROP ', sql.upper())

    def test_missing_directory_is_reported_after_restore(self):
        row = dict(workspace_id=str(uuid4()), root_path=str(Path.cwd() / 'definitely-missing-workspace'),
                   writable=False, execution_mode='disabled')
        with patch.object(workspaces, 'require_workspace', return_value=row):
            with self.assertRaises(workspaces.WorkspaceUnavailableError):
                workspaces.restore_workspace('offline', row['workspace_id'])


class TerminalToolTests(unittest.TestCase):
    def test_unbound_and_disabled_workspaces_never_reach_executor(self):
        executor = MagicMock()
        tool = build_terminal_tool(executor)
        with self.assertRaises(ToolException):
            tool.invoke({'command': 'Get-Location'})
        workspace = open_workspace(Path.cwd())
        with self.assertRaises(ToolException):
            tool.invoke({'command': 'Get-Location'}, config={'configurable': {'workspace': workspace}})
        executor.assert_not_called()

    def test_permissions_are_refreshed_before_each_command(self):
        workspace_id = str(uuid4())
        enabled = open_workspace(Path.cwd(), writable=True, workspace_id=workspace_id, execution_mode='local')
        disabled = open_workspace(Path.cwd(), workspace_id=workspace_id)
        executor = MagicMock()
        tool = build_terminal_tool(executor)
        with self.assertRaises(ToolException):
            tool.invoke({'command': 'Get-Location'}, config={'configurable': {
                'workspace': enabled, 'workspace_loader': lambda: disabled,
            }})
        executor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
