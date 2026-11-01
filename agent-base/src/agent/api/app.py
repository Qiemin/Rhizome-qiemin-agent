import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg import Error as DatabaseError

from .. import __version__
from ..config import PROJECT_ROOT
from ..services.locking import SessionBusyError
from ..storage.sessions import SessionNotFoundError
from ..storage.workspaces import WorkspaceConflictError, WorkspaceNotFoundError
from .lifespan import lifespan
from .routers import chat, sessions, workspaces

logger = logging.getLogger(__name__)
WEB_DIST = PROJECT_ROOT.parent / "agent-web" / "dist"


def create_app() -> FastAPI:
    application = FastAPI(title="Rhizome Qiemin Agent", version=__version__, lifespan=lifespan)
    application.include_router(sessions.router)
    application.include_router(chat.router)
    application.include_router(workspaces.router)

    @application.exception_handler(WorkspaceNotFoundError)
    async def workspace_not_found(request: Request, exc: WorkspaceNotFoundError):
        return JSONResponse(status_code=404, content={"detail": "工作区不存在"})

    @application.exception_handler(WorkspaceConflictError)
    async def workspace_conflict(request: Request, exc: WorkspaceConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(SessionNotFoundError)
    async def session_not_found(request: Request, exc: SessionNotFoundError):
        return JSONResponse(status_code=404, content={"detail": "会话不存在"})

    @application.exception_handler(SessionBusyError)
    async def session_busy(request: Request, exc: SessionBusyError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(DatabaseError)
    async def database_error(request: Request, exc: DatabaseError):
        logger.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "暂时无法访问会话数据，请稍后重试"})

    @application.get("/", include_in_schema=False)
    def frontend():
        index = WEB_DIST / "index.html"
        if not index.is_file():
            return JSONResponse(status_code=503, content={"detail": "前端尚未构建，请在 agent-web 目录执行 npm install 和 npm run build"})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    application.mount("/assets", StaticFiles(directory=WEB_DIST / "assets", check_dir=False), name="assets")
    return application


app = create_app()
