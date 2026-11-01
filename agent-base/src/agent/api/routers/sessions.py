from fastapi import APIRouter, Depends, Query, Response

from ...services.locking import session_guard
from ...storage import sessions as store
from ...storage.messages import load_messages
from ..dependencies import get_database_url
from ..schemas.workspaces import SessionWorkspaceUpdate
from ..schemas.sessions import (
    MessageList,
    MessageResponse,
    SessionCreate,
    SessionList,
    SessionRename,
    SessionResponse,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
def create_session(body: SessionCreate, database_url: str = Depends(get_database_url)):
    return store.create_session(database_url, body.title, body.workspace_id)


@router.put("/{session_id}/workspace", response_model=SessionResponse)
def bind_workspace(session_id: str, body: SessionWorkspaceUpdate,
                   database_url: str = Depends(get_database_url)):
    with session_guard(session_id):
        return store.bind_workspace(database_url, session_id, body.workspace_id)


@router.get("", response_model=SessionList)
def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    database_url: str = Depends(get_database_url),
):
    return store.list_sessions(database_url, limit, offset)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, database_url: str = Depends(get_database_url)):
    return store.require_session(database_url, session_id)


@router.patch("/{session_id}", response_model=SessionResponse)
def rename_session(session_id: str, body: SessionRename, database_url: str = Depends(get_database_url)):
    with session_guard(session_id):
        return store.rename_session(database_url, session_id, body.title)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, database_url: str = Depends(get_database_url)):
    with session_guard(session_id):
        store.delete_session(database_url, session_id)
    return Response(status_code=204)


@router.get("/{session_id}/messages", response_model=MessageList)
def get_messages(session_id: str, database_url: str = Depends(get_database_url)):
    with session_guard(session_id):
        store.require_session(database_url, session_id)
        messages = load_messages(database_url, session_id)
    roles = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system"}
    return MessageList(
        session_id=session_id,
        messages=[
            MessageResponse(
                id=message.id or f"{session_id}:{index}",
                role=roles.get(message.type, message.type),
                content=message.text,
                name=message.name,
                tool_calls=getattr(message, "tool_calls", []),
            )
            for index, message in enumerate(messages)
        ],
    )
