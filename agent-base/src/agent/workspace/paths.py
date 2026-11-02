from pathlib import Path

from .workspace import Workspace


def resolve_workspace_path(
    workspace: Workspace,
    relative_path: str | Path    
) -> Path:
    candidate = Path(relative_path)

    if candidate.anchor:
        raise ValueError("文件路径必须是相对于工作区的相对路径")

    target = (workspace.root / candidate).resolve(strict=False)

    if not target.is_relative_to(workspace.root):
        raise PermissionError("文件路径超出工作区范围")

    return target