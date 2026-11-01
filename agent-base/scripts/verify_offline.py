"""离线检查脚手架；不读取真实 .env，不连接模型服务或 PostgreSQL。"""

import ast
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from agent import config
from agent.graph.builder import build_graph
from agent.tools.tools import TOOLS
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_to_dict,
    messages_from_dict,
)


class FakeModel:
    def __init__(self):
        self.inputs = []
        self.bind_count = 0

    def bind_tools(self, tools):
        assert tools is TOOLS
        self.bind_count += 1
        return self

    def invoke(self, messages):
        self.inputs.append(list(messages))
        last = messages[-1]
        if isinstance(last, ToolMessage):
            assert last.tool_call_id == "offline-terminal"
            assert "未绑定工作区" in last.content
            return AIMessage(content="workspace required")
        if last.content == "terminal request":
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "run_terminal",
                    "args": {"command": "Write-Output 'offline'"},
                    "id": "offline-terminal",
                    "type": "tool_call",
                }],
            )
        return AIMessage(content="offline reply")


def check_syntax():
    paths = [*sorted((ROOT / "src" / "agent").rglob("*.py")),
             *sorted((ROOT / "scripts").glob("*.py"))]
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    print(f"PASS: syntax of {len(paths)} Python files")


def check_graph():
    model = FakeModel()
    graph = build_graph(model)
    first = graph.invoke({"messages": [HumanMessage(content="first")]})
    assert [m.type for m in first["messages"]] == ["human", "ai"]
    assert isinstance(model.inputs[0][0], SystemMessage)
    independent = graph.invoke({"messages": [HumanMessage(content="independent")]})
    assert len(independent["messages"]) == 2
    continued = graph.invoke({
        "messages": [*first["messages"], HumanMessage(content="second")]
    })
    assert len(continued["messages"]) == 4
    assert [m.content for m in model.inputs[-1][1:]] == [
        "first", "offline reply", "second"
    ]
    result = graph.invoke({"messages": [HumanMessage(content="terminal request")]})
    assert [m.type for m in result["messages"]] == ["human", "ai", "tool", "ai"]
    assert result["messages"][-1].content == "workspace required"
    assert model.bind_count == 1
    assert all(sum(isinstance(m, SystemMessage) for m in messages) == 1
               for messages in model.inputs)
    print("PASS: plain replies, explicit history, unbound-workspace rejection, and tool loop termination")

    payload = json.loads(json.dumps([message_to_dict(m) for m in result["messages"]]))
    restored = messages_from_dict(payload)
    assert restored == result["messages"]
    resumed = graph.invoke({"messages": [*restored, HumanMessage(content="continue")]})
    assert len(resumed["messages"]) == 6
    assert resumed["messages"][-1].content == "offline reply"
    print("PASS: tool-call IDs, tool results, and message ordering survive JSON round-trip")


def check_config():
    environment = {"OPENAI_MODEL": "offline", "OPENAI_API_KEY": "offline-key"}
    with patch.dict(os.environ, environment, clear=True), patch.object(config, "load_dotenv") as dotenv:
        settings = config.load_settings()
        assert settings.database_url is None
        assert settings.base_url == "https://api.openai.com/v1"
        assert settings.proxy is None
        assert "offline-key" not in repr(settings)
        dotenv.assert_called_with(config.PROJECT_ROOT / ".env", override=False)
        try:
            config.load_database_url()
        except ValueError as exc:
            assert "DATABASE_URL" in str(exc)
        else:
            raise AssertionError("Missing database URL must fail initialization")

    test_url = "postgresql://offline:offline-password@localhost/unused"
    with patch.dict(os.environ, {"DATABASE_URL": test_url}, clear=True), patch.object(config, "load_dotenv"):
        assert config.load_database_url() == test_url
    with patch.dict(os.environ, {**environment, "DATABASE_URL": test_url}, clear=True), patch.object(config, "load_dotenv"):
        settings = config.load_settings()
        assert settings.database_url == test_url
        assert "offline-password" not in repr(settings)
        assert "offline-key" not in repr(settings)
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///unused"}, clear=True), patch.object(config, "load_dotenv"):
        try:
            config.load_database_url()
        except ValueError:
            pass
        else:
            raise AssertionError("Non-PostgreSQL URL must be rejected")
    print("PASS: configuration defaults, required PostgreSQL URL, and secret-safe repr")


def main():
    check_syntax()
    check_graph()
    check_config()
    import unittest
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("Python:", sys.version.split()[0])
    for package in ("langchain-core", "langchain-openai", "langgraph", "httpx", "python-dotenv", "psycopg"):
        print(f"{package}: {importlib.metadata.version(package)}")
    print("All offline checks passed. No real .env, database connection, or model API was used.")


if __name__ == "__main__":
    main()
