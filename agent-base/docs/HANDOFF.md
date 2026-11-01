# Agent Lab 交接

## 当前决策

- 项目目录：`D:\pyprojject\agent-lab`；包名 `agent_lab`，版本 `0.1.0`。
- 用户已决定把本项目定型为基础脚手架；固定 Git 标签为 `scaffold-v0.1.0`。用户另开项目，目标是类似 Codex 的本地通用 Agent。不要在当前仓库继续添加文件或 Shell 工具。
- 本次授权范围为整理脚手架、离线验证、文档和复用基线，以及提交并推送远程。新项目由用户自己创建。
- 默认继续采用小步骤教学，除非用户明确委托直接修改。保护用户手写实现和真实本机配置。

## 现有实现

- `config.py`：环境优先的 `.env` 配置；`Settings.api_key` 和 `database_url` 均隐藏 repr。CLI 需要模型和数据库配置；`load_database_url()` 允许建表时只配置数据库。
- `model.py`：`ChatOpenAI` 工厂，沿用 Responses API、外部同步 httpx 客户端、60 秒超时和一次重试。
- `state.py`：`messages` 使用 `add_messages` 合并。
- `tools.py`：`TOOLS = [multiply]`，是模型声明和 `ToolNode` 的统一来源。
- `graph.py`：模型绑定在图创建时执行一次。流程为 START → chat；有工具调用则 tools → chat，没有则 END。没有 checkpointer。
- `storage.py`：PostgreSQL JSONB 消息表；`(session_id, position)` 联合主键。保存时在一个事务内删除并重写指定会话；读取时按 position 排序，再恢复消息对象。
- `cli.py`：选择会话、读取历史、处理多轮输入、每轮成功后保存完整历史。支持空输入提示、`/exit`、EOF / Ctrl+C，以及数据库异常分类。只有保存成功才更新当前进程的 history。
- `scripts/init_db.py`：只连接已有数据库并建表；不启动服务、不创建数据库、不请求模型，不输出原始连接异常。
- `scripts/verify_offline.py`：已适配工具循环和 CLI 持久化，使用假模型及模拟数据库。无需真实配置。

## 验证事实

2026-10-30，用户报告已完成：PostgreSQL 专用账号和数据库连接、消息表初始化、CLI 同会话退出重启恢复成功。

协作助手完成的离线验证包括：11 个 Python 文件语法、普通回复、显式历史传递、实际本地乘法工具执行、工具结果回传和图结束、工具消息 JSON 往返、模拟数据库下的 CLI 重启恢复与隔离、保存失败、空输入、退出和配置隐藏敏感字段。`pip check` 通过。

协作助手未读取真实 `.env`，未调用真实模型或读取聊天数据库。本轮没有新增真实模型工具调用、数据库事务回滚或线上部署验收，不得把离线替身检查写成真实服务验证。

运行环境：Windows / Python 3.14.0；langchain-core 1.7.3、langchain-openai 1.7.3、langgraph 1.2.18、httpx 0.28.1、python-dotenv 1.2.4、psycopg 3.3.6。当前运行时包版本约束见根目录 `constraints-windows-py314.txt`。

## 已知边界与下一项目

这是一份单用户 CLI 脚手架。同一会话按单进程使用设计，尚无并发写控制；保存每轮完整历史，尚无增量优化和摘要。没有应用级长期记忆、通用文件工具、Shell 工具、权限审批、费用预算或完善诊断日志。

下一项目复用流程见 `docs/REUSE.md`。不要复制 `.env`、`.venv`、聊天记录或数据库。需要文件、命令执行等能力时，在新项目先确定工作目录和执行边界，再按教学小步骤推进；不要把任意 Shell 执行直接加入此基线。
