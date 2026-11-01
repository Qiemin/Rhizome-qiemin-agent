from fastapi import APIRouter, Depends, HTTPException, Query

from ...services.locking import SessionBusyError, session_guard
from ...storage import workspaces as store
from ..dependencies import get_database_url
from ..schemas.workspaces import (
    WorkspaceCreate,
    WorkspaceList,
    WorkspaceResponse,
    WorkspaceSettings,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=201)
def create_workspace(body: WorkspaceCreate, database_url: str = Depends(get_database_url)):
    try:
        return store.create_workspace(database_url, **body.model_dump())
    except store.WorkspaceConflictError:
        raise
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="工作区必须是存在且可访问的绝对目录路径") from exc


@router.get("", response_model=WorkspaceList)
def list_workspaces(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    database_url: str = Depends(get_database_url),
):
    return store.list_workspaces(database_url, limit, offset)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: str, database_url: str = Depends(get_database_url)):
    return store.require_workspace(database_url, workspace_id)


@router.put("/{workspace_id}/settings", response_model=WorkspaceResponse)
def update_settings(workspace_id: str, body: WorkspaceSettings,
                    database_url: str = Depends(get_database_url)):
    try:
        with session_guard("workspace:" + workspace_id):
            return store.update_settings(database_url, workspace_id, **body.model_dump())
    except SessionBusyError as exc:
        raise HTTPException(status_code=409, detail="工作区正在执行命令，请稍后修改设置") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="工作区目录或执行设置不可用") from exc
