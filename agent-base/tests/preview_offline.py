"""Manual UI QA server on port 8765, backed exclusively by test doubles."""

import sys
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path
from time import sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

import uvicorn
from langchain_core.messages import AIMessage, AIMessageChunk
from agent.api.app import create_app
from agent.api.dependencies import get_database_url, get_graph
from test_api import MemoryStore, install_memory


class PreviewGraph:
    def stream(self, state, **kwargs):
        text = '你好，这是前端验收使用的测试回复。\n\n会话管理、流式接收与历史恢复已接入同一组接口。实际运行时，这里会显示你配置的模型生成的内容。'
        for char in text:
            sleep(0.025)
            yield {'type': 'messages', 'data': (AIMessageChunk(content=char), {'langgraph_node': 'chat'})}
        yield {'type': 'values', 'data': {'messages': [*state['messages'], AIMessage(content=text)]}}


@asynccontextmanager
async def no_external_resources(app):
    yield


if __name__ == '__main__':
    with ExitStack() as stack:
        memory = MemoryStore()
        install_memory(stack, memory)
        app = create_app()
        app.router.lifespan_context = no_external_resources
        app.dependency_overrides[get_database_url] = lambda: 'offline'
        app.dependency_overrides[get_graph] = lambda: PreviewGraph()
        uvicorn.run(app, host='127.0.0.1', port=8765, log_level='warning')
