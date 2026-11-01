from collections.abc import Callable
from dataclasses import asdict

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException, tool

from ..execution.models import CommandResult
from ..services.locking import SessionBusyError, session_guard
from ..workspace.workspace import Workspace


def build_terminal_tool(
    execute_command: Callable[[str, Workspace], CommandResult],
) -> BaseTool:

    @tool
    def run_terminal(command: str, config: RunnableConfig) -> dict:
        """执行一条 PowerShell 命令，返回输出、退出码及超时、截断信息。"""
        if not command.strip():
            raise ToolException("命令不能为空")
        workspace = config.get("configurable", {}).get("workspace")
        if not isinstance(workspace, Workspace):
            raise ToolException("当前会话未绑定工作区，请用户先选择工作区")
        try:
            with session_guard("workspace:" + str(workspace.workspace_id)):
                loader = config.get("configurable", {}).get("workspace_loader")
                if loader is not None:
                    workspace = loader()
                if workspace.execution_mode != "local" or not workspace.writable:
                    raise ToolException("当前工作区未启用本地终端执行，请用户检查工作区设置")
                result = execute_command(command, workspace)
        except SessionBusyError as exc:
            raise ToolException("这个工作区正在执行另一条命令，请稍后重试") from exc
        except (OSError, ValueError, RuntimeError) as exc:
            raise ToolException(str(exc)) from exc
        return asdict(result)

    return run_terminal
