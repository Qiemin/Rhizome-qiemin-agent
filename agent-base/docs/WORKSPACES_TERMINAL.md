# 工作区保存与本地终端工具

当前后端已接通：工作区登记和设置保存 → 会话绑定 → 聊天时从数据库恢复 → 图注入运行配置 → 终端执行 → 工具消息持久化。

当前终端提供 `local` 模式，使用 Windows 当前用户权限。工作区是起始目录，不是系统级文件权限边界；Job Object 管理进程，venv 隔离 Python 依赖。AppContainer 等目录权限隔离尚未完成。

## 数据保存位置

| 数据 | 位置 |
|---|---|
| 工作区 ID、名称、真实目录、写入策略、终端模式 | PostgreSQL `workspaces` |
| 会话选择的工作区 | PostgreSQL `sessions.workspace_id` |
| 用户文件与命令生成的文件 | 用户选择的真实目录 |
| 工作区独立 Python 环境 | `%LOCALAPPDATA%\Rhizome\runtimes\<workspace_id>` |
| 对话与工具调用/返回 | 原有 PostgreSQL `messages` |

一个工作区可以供多个会话使用。服务重启后根据会话关联重新加载配置，同一工作区的 Python 环境和文件继续保留。目录移动或不可访问时明确报错，不会回退到项目目录。

## 首次使用新表结构

同步源码不会自动修改真实数据库。首次使用工作区接口前，在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -B scripts\init_db.py
```

初始化会创建 `workspaces`，为已有 `sessions` 增加可空的 `workspace_id` 外键；旧会话、消息保留。`CREATE TABLE IF NOT EXISTS` 不会给旧表增加字段，因此使用一条 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`。

## API 使用流程

前端“资源库”可登记和设置工作区；输入框下方可选择或解绑会话工作区。也可通过 `http://127.0.0.1:8000/docs` 操作以下接口。

1. `POST /api/v1/workspaces` 保存真实存在的目录，并取得后端生成的 ID。

```json
{
  "name": "办公资料",
  "root_path": "D:\\办公资料",
  "writable": true,
  "execution_mode": "local"
}
```

默认是 `writable=false`、`execution_mode=disabled`。上例显式开启本地终端；它可访问当前用户有权限访问的其他路径，不是只读或目录隔离沙箱。

2. `POST /api/v1/sessions` 创建并关联会话。

```json
{"title": "整理办公资料", "workspace_id": "替换成保存的工作区ID"}
```

已有会话用 `PUT /api/v1/sessions/{session_id}/workspace` 绑定，内容为 `{"workspace_id":"工作区ID"}`；解绑时发送 `{"workspace_id":null}`。

3. 沿用 `POST /api/v1/sessions/{session_id}/messages`，只传 `message`。例如要求终端输出当前目录。服务从数据库恢复目录，模型只提供 command，不能通过工具参数指定工作区和权限。

4. 使用 `GET /api/v1/workspaces`、`GET /api/v1/workspaces/{id}`、`GET /api/v1/sessions/{id}` 核对配置与关联；服务重启后再次查询、继续同一会话验收恢复。

修改工作区设置使用 `PUT /api/v1/workspaces/{id}/settings`，提交完整的 `name`、`writable`、`execution_mode`；不在这里改变目录。正在执行命令时返回 409，每次工具执行前会重新读取设置。

## 工具执行方式

- 默认超时 60 秒，stdout、stderr 各保存前 64 KiB，超出继续读取并丢弃，结果标记截断。
- 受信任的 Python 引导进程先等待信号；加入 Job 后才开始创建环境、启动 PowerShell。失败时不退回无 Job 执行。
- 普通后台子进程在命令结束时清理，超时终止管理组。通过外部系统服务启动的进程不属于完整保证范围。
- 每条命令单独启动，cd、PowerShell 变量不跨调用保留。文件和独立 Python 环境保留，python/pip 优先使用该工作区环境。
- 子进程环境变量经过筛选，不直接继承模型密钥、数据库 URL 等后端配置；这不等于限制命令读取主机文件。
- 停止接收 SSE 不等于立即终止正在运行的命令。

## 验证

```powershell
.\.venv\Scripts\python.exe -B scripts\verify_offline.py
.\.venv\Scripts\python.exe -m pip check
```

离线脚本使用数据库、模型和命令执行替身，不读取真实 .env，不连接真实模型或 PostgreSQL。覆盖工作区登记、设置、会话关联、恢复、运行配置注入及工具循环。

真实 Windows 进程检查只使用自建临时目录，也不连接数据库或模型：

```powershell
.\.venv\Scripts\python.exe -B scripts\verify_terminal_local.py
```

核对已存入 PostgreSQL 的工作区并手动调用真实工具：

```powershell
.\.venv\Scripts\python.exe -B scripts\verify_terminal.py --workspace-id "工作区ID" --command "Get-Location"
```

最后一条会读取本机数据库配置并查询真实工作区记录，不请求模型。

## 后续审查顺序

1. [建表与字段](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/storage/storage.py)
2. [工作区存储](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/storage/workspaces.py) 和 [会话绑定](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/storage/sessions.py)
3. [工作区 API](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/api/routers/workspaces.py)
4. [聊天恢复与注入](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/services/chat.py)
5. [工具入口与配置检查](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/tools/terminal.py)
6. [执行器](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/execution/runner.py)、[Job 管理](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/execution/windows_job.py) 和 [输出缓冲](D:/pyprojject/Rhizome-qiemin-agent/agent-base/src/agent/execution/output.py)

`CreateJobObject(None, "")` 使用 pywin32 接受的空字符串名称；之前传入 None 的写法已修正。
