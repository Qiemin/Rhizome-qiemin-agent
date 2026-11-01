"""Verify migrations and transactions in a temporary schema, never user histories."""

import re
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import psycopg
from agent.config import load_database_url
from agent.storage import sessions
from agent.storage.storage import init_db
from agent.storage.messages import load_messages, save_messages
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    message_to_dict,
)
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb


def main() -> int:
    schema = 'rhizome_verify_' + uuid4().hex
    assert re.fullmatch(r'rhizome_verify_[0-9a-f]{32}', schema)
    created = False
    try:
        database_url = load_database_url()
        test_url = make_conninfo(database_url, options=f'-c search_path={schema}')
        with psycopg.connect(database_url, connect_timeout=10, autocommit=True) as admin:
            try:
                admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
                created = True
                with psycopg.connect(test_url, connect_timeout=10) as connection:
                    connection.execute('''
                        CREATE TABLE messages (
                            session_id TEXT NOT NULL,
                            position BIGINT NOT NULL CHECK (position >= 0),
                            message_json JSONB NOT NULL,
                            PRIMARY KEY (session_id, position)
                        )
                    ''')
                    connection.execute(
                        'INSERT INTO messages VALUES (%s, %s, %s)',
                        ('legacy', 0, Jsonb(message_to_dict(HumanMessage(content='legacy test only')))),
                    )
                init_db(test_url)
                sessions.rename_session(test_url, 'legacy', 'Retained title')
                init_db(test_url)
                assert sessions.require_session(test_url, 'legacy')['title'] == 'Retained title'
                assert load_messages(test_url, 'legacy')[0].content == 'legacy test only'
                print('PASS: old message-only schema migration, repeated initialization, and title preservation')

                session = sessions.create_session(test_url)
                session_id = session['session_id']
                history = [
                    HumanMessage(content='First question'),
                    AIMessage(content='', tool_calls=[{'name': 'multiply', 'args': {'a': 2, 'b': 3}, 'id': 't1', 'type': 'tool_call'}]),
                    ToolMessage(content='6', tool_call_id='t1'),
                    AIMessage(content='6'),
                ]
                save_messages(test_url, session_id, history)
                assert load_messages(test_url, session_id) == history
                before = sessions.require_session(test_url, session_id)
                assert before['title'] == 'First question' and before['message_count'] == 4
                with psycopg.connect(test_url, connect_timeout=10) as connection:
                    connection.execute('ALTER TABLE messages ADD CONSTRAINT verify_position CHECK (position < 5)')
                try:
                    save_messages(test_url, session_id, [*history, HumanMessage(content='next'), AIMessage(content='next reply')])
                except psycopg.errors.CheckViolation:
                    pass
                else:
                    raise AssertionError('Expected a real database failure')
                assert load_messages(test_url, session_id) == history
                assert sessions.require_session(test_url, session_id) == before
                print('PASS: tool JSON round-trip and atomic rollback of messages plus session metadata')

                with psycopg.connect(test_url, connect_timeout=10) as connection:
                    connection.execute('ALTER TABLE messages DROP CONSTRAINT verify_position')
                sessions.rename_session(test_url, session_id, 'Manual name')
                save_messages(test_url, session_id, history)
                assert sessions.require_session(test_url, session_id)['title'] == 'Manual name'
                sessions.delete_session(test_url, session_id)
                assert load_messages(test_url, session_id) == []
                assert sessions.get_session(test_url, session_id) is None
                try:
                    save_messages(test_url, session_id, history)
                except sessions.SessionNotFoundError:
                    pass
                else:
                    raise AssertionError('Deleted sessions must not be recreated by a late save')
                assert sessions.list_sessions(test_url, limit=1)['total'] == 1
                print('PASS: CRUD, pagination, cascading deletion, and no deleted-session resurrection')
            finally:
                if created:
                    # Only the schema generated above in this run can be removed.
                    admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        print('All PostgreSQL checks passed; the temporary schema was removed. No user messages were read.')
        return 0
    except Exception as exc:
        print(f'PostgreSQL verification failed: {type(exc).__name__}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
