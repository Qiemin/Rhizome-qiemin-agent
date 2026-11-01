# 从脚手架开始一个新项目

本页是用户自行创建新项目时的操作说明；本次整理没有创建新项目。

## 1. 获取固定版本

使用 Git 标签 `scaffold-v0.1.0` 的源码 ZIP，或者整理时生成的本地 `releases/agent-lab-scaffold-v0.1.0.zip`。解压到你选择的新目录。Git 源码归档不含旧 `.git`、`.env`、`.venv`、缓存、数据库、聊天记录和日志。

不要直接复制整个旧项目目录：旧虚拟环境中的可编辑安装可能仍指向原项目，旧数据库也可能包含原会话。

## 2. 调整项目身份

在新目录中修改 `pyproject.toml` 的项目名、说明和命令入口名称。首次复用可以保留 `agent_lab` 包名，独立虚拟环境能隔离两个项目；如果重命名包目录，需要同步脚本中的导入、命令入口和运行文档。

更新 README、AGENTS 和交接文档，使其描述新应用，而不是继续引用旧项目的本机路径和“基础脚手架冻结”约定。以新应用自己的版本与验收记录为准。

## 3. 创建独立环境和配置

在新项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

若使用 Windows / Python 3.14，可选择 `pip install -e . -c constraints-windows-py314.txt` 尽量复现已验证环境；其他平台重新安装和验证。

仅在尚无 `.env` 时从空值模板创建：

```powershell
Copy-Item -LiteralPath '.env.example' -Destination '.env'
```

在本机填写模型和数据库配置，不复制旧项目的真实 `.env`。为新应用准备独立数据库和账号；如果把新应用指向旧数据库，同名 session_id 会共用同一份记录。

## 4. 验证后初始化

```powershell
.\.venv\Scripts\python.exe -B scripts/verify_offline.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe -m agent_lab
```

前两项不需要真实模型或数据库；后两项分别连接数据库和运行真实模型，配置好后由用户执行。若已重命名包，最后一条相应调整。

从 ZIP 创建的项目没有旧 Git 历史。可以在新目录运行 `git init`，并配置新仓库的远程地址，再按自己的发布流程提交。

## 5. 开始应用开发

基线的工具入口是 `src/agent_lab/tools.py` 的 `TOOLS` 列表。新应用从明确的首个任务开始，逐项添加工具与验收。用户当前意向是类似 Codex 的本地通用助手，可先做工作目录内的浏览、读取和搜索，再设计文件写入、命令执行及权限控制。

调整图后同步更新离线验证，继续区分“工具本地运行”“假模型图流程”和“真实模型端到端运行”。保留 PostgreSQL 消息归档与 LangGraph 执行恢复之间的职责边界。
