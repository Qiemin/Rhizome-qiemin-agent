from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkspaceSettings(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    writable: bool = False
    execution_mode: Literal["disabled", "local"] = Field(
        default="disabled",
        description="disabled 禁用终端；local 使用本机用户权限执行，不是目录隔离沙箱。",
    )

    @model_validator(mode="after")
    def check_terminal_permissions(self):
        if self.execution_mode == "local" and not self.writable:
            raise ValueError("本地终端可修改文件，不能对只读工作区启用")
        return self


class WorkspaceCreate(WorkspaceSettings):
    root_path: str = Field(min_length=1, max_length=4096)


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    root_path: str
    writable: bool
    execution_mode: Literal["disabled", "local"]
    created_at: datetime


class WorkspaceList(BaseModel):
    items: list[WorkspaceResponse]
    total: int
    limit: int
    offset: int


class SessionWorkspaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str | None = Field(max_length=100)
