from collections.abc import Iterator
from contextlib import closing

from langchain_core.messages import HumanMessage

from ..storage.messages import load_messages, save_messages
from ..storage.sessions import require_session
from ..storage.workspaces import restore_workspace
from .locking import session_guard


def stream_turn(
    graph,
    database_url: str,
    session_id: str,
    question: str,
) -> Iterator[dict[str, str]]:
    question = question.strip()
    if not question:
        raise ValueError("输入不能为空")

    with session_guard(session_id):
        session = require_session(database_url, session_id)
        workspace_id = session.get("workspace_id")
        workspace = (
            restore_workspace(database_url, workspace_id)
            if workspace_id else None
        )
        workspace_loader = (
            (lambda: restore_workspace(database_url, workspace_id))
            if workspace_id else None
        )
        history = load_messages(database_url, session_id)
        final_messages = None
        with closing(graph.stream(
            {"messages": [*history, HumanMessage(content=question)]},
            config={"configurable": {"workspace": workspace, "workspace_loader": workspace_loader}},
            stream_mode=["messages", "values"],
            version="v2",
        )) as stream:
            for part in stream:
                if part["type"] == "messages":
                    chunk, metadata = part["data"]
                    if metadata.get("langgraph_node") == "chat" and chunk.text:
                        yield {"event": "delta", "text": chunk.text}
                elif part["type"] == "values":
                    final_messages = part["data"]["messages"]
        if final_messages is None:
            raise RuntimeError("未取得对话执行结果")
        save_messages(database_url, session_id, final_messages)
        yield {"event": "done", "session_id": session_id}

