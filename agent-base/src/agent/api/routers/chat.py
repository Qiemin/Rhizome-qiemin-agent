import json
import logging

from anyio import CancelScope
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from ...services.chat import stream_turn
from ...services.locking import SessionBusyError
from ...storage.sessions import SessionNotFoundError, require_session
from ...storage.workspaces import WorkspaceNotFoundError, WorkspaceUnavailableError
from ..dependencies import get_database_url, get_graph
from ..schemas.chat import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/sessions",
    tags=["chat"],
)


def encode_sse(event: dict[str, str]) -> str:
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event['event']}\ndata: {data}\n\n"


@router.post(
    "/{session_id}/messages",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def send_message(
    session_id: str,
    body: ChatRequest,
    graph=Depends(get_graph),
    database_url: str = Depends(get_database_url),
) -> StreamingResponse:
    require_session(database_url, session_id)

    async def generate_events():
        stream = stream_turn(
            graph=graph,
            database_url=database_url,
            session_id=session_id,
            question=body.message,
        )
        try:
            async for event in iterate_in_threadpool(stream):
                yield encode_sse(event)
        except (SessionBusyError, SessionNotFoundError) as exc:
            yield encode_sse({
                "event": "error",
                "message": "会话正在执行其他操作，请稍后再试" if isinstance(exc, SessionBusyError) else "会话已不存在",
            })
        except (WorkspaceNotFoundError, WorkspaceUnavailableError) as exc:
            yield encode_sse({
                "event": "error",
                "message": "工作区不存在，请重新绑定" if isinstance(exc, WorkspaceNotFoundError) else str(exc),
            })
        except Exception as exc:
            logger.error("流式对话失败：%s", type(exc).__name__)

            yield encode_sse(
                {
                    "event": "error",
                    "message": "对话执行失败，请查看服务端日志",
                }
            )
        finally:
            with CancelScope(shield=True):
                await run_in_threadpool(stream.close)

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
