from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path
    writable: bool = False
    workspace_id: str | None = None
    execution_mode: str = "disabled"


def open_workspace(
    directory: str | Path,
    *,
    writable: bool = False,
    workspace_id: str | None = None,
    execution_mode: str = "disabled",
) -> Workspace:
    root = Path(directory).expanduser()
    
    if not root.is_absolute():
        raise ValueError("工作区必须使用绝对路径")

    root = root.resolve(strict=True)

    if not root.is_dir():
        raise NotADirectoryError("工作区必须是一个文件夹")

    if execution_mode not in {"disabled", "local"}:
        raise ValueError("不支持的执行模式")
    if execution_mode == "local" and not writable:
        raise ValueError("本地终端可修改文件，不能对只读工作区启用")

    return Workspace(root, writable, workspace_id, execution_mode)

