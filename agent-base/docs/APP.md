# 会话 API 与 Vue 工作区

## 本地运行

在 agent-base 目录执行：

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe -m agent
```

前端先在相邻的 agent-web 目录执行 `npm ci` 和 `npm run build`，随后访问 `http://127.0.0.1:8000/`。开发时也可使用前端的 `npm run dev`，默认端口 5173。

初始化会创建 sessions、messages、会话排序索引及外键。在同一事务中从已有 messages 补建 sessions；重复运行保持已有标题、时间和消息。旧数据没有可恢复的真实会话创建时间，补建记录使用迁移时间。删除会话会级联删除消息。

## 接口

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | /health | HTTP 进程健康检查，不代表已验证模型或数据库连接 |
| POST | /api/v1/sessions | `{ "title": "新会话" }`，返回 201 和后端生成的会话 ID |
| GET | /api/v1/sessions | limit（1–100，默认 50）、offset；返回 items、total、limit、offset |
| GET | /api/v1/sessions/{id} | 会话元数据及消息数量 |
| PATCH | /api/v1/sessions/{id} | `{ "title": "新名称" }` |
| DELETE | /api/v1/sessions/{id} | 删除会话及消息，返回 204 |
| GET | /api/v1/sessions/{id}/messages | 按位置返回消息，包括工具调用与结果 |
| POST | /api/v1/sessions/{id}/messages | `{ "message": "你好" }`，返回 SSE |

会话不存在返回 404，输入无效返回 422，非流式操作遇到会话忙碌返回 409，数据库操作失败返回 503。聊天必须使用已创建的会话 ID；迁移前已有的 ID 会保留。发送消息长度上限为 32000 字符，标题上限为 200 字符。

SSE：delta 携带 text，done 携带 session_id，error 携带 message。流开始后的错误（包括此时才检测到的会话争用）通过 error 事件通知，HTTP 状态码不再改变。done 仅在消息和会话元数据共同提交后发出；模型执行失败或保存失败不会发送 done。完整 LangChain JSON 消息被保存，不使用前端拼接文本替代工具历史。默认标题在首次保存时取首条用户消息的前 40 字符，人工改名会保留。

## 验证

```powershell
.\.venv\Scripts\python.exe -B scripts/verify_offline.py
.\.venv\Scripts\python.exe -m pip check
```

离线脚本不读取真实 .env，不连接真实数据库和模型。它检查图与工具循环、配置、会话 CRUD、接口校验、流式完成和失败语义、工具历史以及中断后的资源释放。

可选真实 PostgreSQL 验证：

```powershell
.\.venv\Scripts\python.exe -B scripts/verify_postgres.py
```

该脚本通过本机配置连接数据库，只在当次生成的临时 schema 中测试迁移、重复运行、外键、事务回滚、消息 JSON 往返和级联删除，随后移除该 schema。数据库账号需有创建 schema 权限。不调用模型、不读取业务消息、不展示连接地址。

## 当前边界

这是本机单用户、单服务进程版本，没有登录或远程部署能力。同一进程中的同会话请求受互斥保护，多个进程或多个服务实例需要数据库锁或任务队列。停止接收不承诺立即终止模型远端推理；中断的本轮不会以半截消息覆盖已保存历史。历史查询目前返回整段会话，大量消息的分页与上下文压缩留待后续实现。

## 存储层模块

- `storage/storage.py`：创建数据库表和索引。
- `storage/sessions.py`：会话元数据的创建、查询、改名和删除。
- `storage/messages.py`：完整消息的序列化、保存和读取；保存消息与更新会话元数据使用同一事务。
