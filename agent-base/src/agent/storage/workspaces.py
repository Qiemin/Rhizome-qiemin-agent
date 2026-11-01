"""Persist workspace registrations; the user's files remain on disk."""

from uuid import uuid4

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from ..workspace.workspace import Workspace, open_workspace


class WorkspaceNotFoundError(LookupError):
    pass


class WorkspaceConflictError(ValueError):
    pass


class WorkspaceUnavailableError(ValueError):
    pass


def create_workspace(database_url: str, name: str, root_path: str,
                     writable: bool = False, execution_mode: str = "disabled") -> dict:
    workspace = open_workspace(root_path, writable=writable, execution_mode=execution_mode)
    try:
        with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
            return connection.execute(
                """INSERT INTO workspaces
                   (workspace_id, name, root_path, writable, execution_mode)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (str(uuid4()), name, str(workspace.root), writable, execution_mode),
            ).fetchone()
    except UniqueViolation as exc:
        raise WorkspaceConflictError("这个目录已经登记为工作区") from exc


def list_workspaces(database_url: str, limit: int = 50, offset: int = 0) -> dict:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        total = connection.execute("SELECT count(*) AS total FROM workspaces").fetchone()["total"]
        items = connection.execute(
            """SELECT * FROM workspaces ORDER BY created_at DESC, workspace_id DESC
               LIMIT %s OFFSET %s""", (limit, offset),
        ).fetchall()
        return {"items": items, "total": total, "limit": limit, "offset": offset}


def require_workspace(database_url: str, workspace_id: str) -> dict:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        row = connection.execute(
            "SELECT * FROM workspaces WHERE workspace_id = %s", (workspace_id,),
        ).fetchone()
    if row is None:
        raise WorkspaceNotFoundError(workspace_id)
    return row


def update_settings(database_url: str, workspace_id: str, name: str,
                    writable: bool = False, execution_mode: str = "disabled") -> dict:
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as connection:
        row = connection.execute(
            "SELECT * FROM workspaces WHERE workspace_id = %s FOR UPDATE", (workspace_id,),
        ).fetchone()
        if row is None:
            raise WorkspaceNotFoundError(workspace_id)
        open_workspace(row["root_path"], writable=writable, execution_mode=execution_mode)
        return connection.execute(
            """UPDATE workspaces SET name = %s, writable = %s, execution_mode = %s
               WHERE workspace_id = %s RETURNING *""",
            (name, writable, execution_mode, workspace_id),
        ).fetchone()


def restore_workspace(database_url: str, workspace_id: str) -> Workspace:
    row = require_workspace(database_url, workspace_id)
    try:
        return open_workspace(
            row["root_path"], writable=row["writable"],
            workspace_id=row["workspace_id"], execution_mode=row["execution_mode"],
        )
    except (OSError, ValueError) as exc:
        raise WorkspaceUnavailableError("工作区目录不可用，请检查目录或重新绑定工作区") from exc
