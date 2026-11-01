"""PostgreSQL table initialization."""

import psycopg


def init_db(database_url: str) -> None:
    """Create the current session/message tables and their indexes."""
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                root_path TEXT NOT NULL UNIQUE,
                writable BOOLEAN NOT NULL DEFAULT FALSE,
                execution_mode TEXT NOT NULL DEFAULT 'disabled'
                    CHECK (execution_mode IN ('disabled', 'local')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (execution_mode <> 'local' OR writable)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '新会话',
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            ALTER TABLE sessions ADD COLUMN IF NOT EXISTS workspace_id TEXT
            REFERENCES workspaces (workspace_id) ON DELETE SET NULL
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                session_id TEXT NOT NULL,
                position BIGINT NOT NULL CHECK (position >= 0),
                message_json JSONB NOT NULL,
                PRIMARY KEY (session_id, position)
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS sessions_updated_at_idx
            ON sessions (updated_at DESC, session_id DESC)
        """)
