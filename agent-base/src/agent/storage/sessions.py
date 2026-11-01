"""Session metadata queries; message content stays in messages.py."""

from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from .workspaces import WorkspaceNotFoundError


class SessionNotFoundError(LookupError):
    """The requested conversation does not exist."""


def create_session(database_url: str, title: str = "新会话", workspace_id: str | None = None) -> dict:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        if workspace_id is not None and connection.execute(
            "SELECT workspace_id FROM workspaces WHERE workspace_id = %s", (workspace_id,),
        ).fetchone() is None:
            raise WorkspaceNotFoundError(workspace_id)
        return connection.execute(
            """
            INSERT INTO sessions (session_id, title, workspace_id) VALUES (%s, %s, %s)
            RETURNING *, 0::bigint AS message_count
            """, (str(uuid4()), title, workspace_id),
        ).fetchone()


def bind_workspace(database_url: str, session_id: str, workspace_id: str | None) -> dict:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        if workspace_id is not None and connection.execute(
            "SELECT workspace_id FROM workspaces WHERE workspace_id = %s", (workspace_id,),
        ).fetchone() is None:
            raise WorkspaceNotFoundError(workspace_id)
        row = connection.execute(
            """UPDATE sessions SET workspace_id = %s, updated_at = clock_timestamp()
               WHERE session_id = %s RETURNING *""", (workspace_id, session_id),
        ).fetchone()
        if row is None:
            raise SessionNotFoundError(session_id)
        row["message_count"] = connection.execute(
            "SELECT count(*) AS count FROM messages WHERE session_id = %s", (session_id,),
        ).fetchone()["count"]
        return row


def list_sessions(database_url: str, limit: int = 50, offset: int = 0) -> dict:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        total = connection.execute("SELECT count(*) AS total FROM sessions").fetchone()["total"]
        items = connection.execute(
            """
            SELECT s.*, (SELECT count(*) FROM messages m
                         WHERE m.session_id = s.session_id) AS message_count
            FROM sessions s ORDER BY s.updated_at DESC, s.session_id DESC
            LIMIT %s OFFSET %s
            """, (limit, offset),
        ).fetchall()
        return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_session(database_url: str, session_id: str) -> dict | None:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        return connection.execute(
            """
            SELECT s.*, (SELECT count(*) FROM messages m
                         WHERE m.session_id = s.session_id) AS message_count
            FROM sessions s WHERE s.session_id = %s
            """, (session_id,),
        ).fetchone()


def require_session(database_url: str, session_id: str) -> dict:
    session = get_session(database_url, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def rename_session(database_url: str, session_id: str, title: str) -> dict:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        session = connection.execute(
            """
            UPDATE sessions SET title = %s, updated_at = clock_timestamp()
            WHERE session_id = %s RETURNING *
            """, (title, session_id),
        ).fetchone()
        if session is None:
            raise SessionNotFoundError(session_id)
        session["message_count"] = connection.execute(
            "SELECT count(*) AS count FROM messages WHERE session_id = %s", (session_id,),
        ).fetchone()["count"]
        return session


def delete_session(database_url: str, session_id: str) -> None:
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        row = connection.execute(
            "DELETE FROM sessions WHERE session_id = %s RETURNING session_id", (session_id,),
        ).fetchone()
        if row is None:
            raise SessionNotFoundError(session_id)
