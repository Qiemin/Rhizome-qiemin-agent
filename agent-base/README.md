# Rhizome Qiemin Agent

基于自写 Agent 脚手架开发的本地办公助手。后端采用 Python、FastAPI、LangGraph 和 PostgreSQL，前端采用 Vue 3 + Vite。

当前已支持：会话新建、列表、改名、删除、历史查询、SSE 流式聊天，以及工具调用消息的完整保存与恢复。会话数据位于 `sessions`，完整消息位于 `messages`。

## 启动

在 `agent-base` 目录，使用已经准备好的独立虚拟环境和本机配置：

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe -m agent
```

前端已构建时，直接打开 [工作区](http://127.0.0.1:8000/)。接口说明位于 [Swagger UI](http://127.0.0.1:8000/docs)。

数据库初始化会创建 workspaces、sessions、messages，并为已有 sessions 增加 workspace_id；已有会话和消息保留。新会话可关联工作区，本地终端默认禁用。

## 前端开发

在相邻的 `agent-web` 目录执行：

```powershell
npm ci
npm run dev
```

开发地址默认为 `http://127.0.0.1:5173/`，API 请求会代理到后端。运行 `npm run build` 后，构建产物由 FastAPI 提供。

## 检查

```powershell
.\.venv\Scripts\python.exe -B scripts/verify_offline.py
.\.venv\Scripts\python.exe -m pip check
```

离线检查使用假模型和模拟数据库，不读取真实配置、不连接真实服务。可选的 `scripts/verify_postgres.py` 使用一次性测试 schema 验证真实数据库迁移与事务，结束后移除测试 schema，不读取业务历史。

前端检查在 `agent-web` 执行 `npm test` 和 `npm run build`。

详细接口、数据迁移与当前边界见 [docs/APP.md](docs/APP.md)，前端说明见相邻 `agent-web/README.md`。当前版本面向本机单用户、单服务进程；多实例运行需要进一步增加数据库层面的执行协调。

`docs/BASELINE.md`、`docs/REUSE.md` 及旧交接文档记录原始脚手架背景；当前应用运行方式以本页和 `docs/APP.md` 为准。

## 工作区与本地终端

工作区保存、会话绑定、终端模式和验收步骤见 [docs/WORKSPACES_TERMINAL.md](docs/WORKSPACES_TERMINAL.md)。
