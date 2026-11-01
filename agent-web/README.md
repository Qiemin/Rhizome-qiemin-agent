# Rhizome 前端

Vue 3 + Vite。会话与消息保存在后端 PostgreSQL；浏览器只记住上次打开的会话 ID。

## 开发

在 `agent-base` 启动后端，再在本目录执行：

```powershell
npm ci
npm run dev
```

访问 Vite 输出的本地地址，默认 `http://127.0.0.1:5173`。`/api`、`/health`、接口文档通过 Vite 代理到 `127.0.0.1:8000`，无需额外配置 CORS。

## 构建

```powershell
npm run build
```

构建到 `dist/`，FastAPI 会在 `http://127.0.0.1:8000/` 提供页面。源码变更后需要重新构建；开发时使用 Vite 可自动更新。

## 检查

```powershell
npm test
npm run build
```

`src/api/sse.js` 负责 UTF-8 流解码与 SSE 事件边界，`src/composables/useChat.js` 管理会话状态，组件位于 `src/components/`。

`delta` 增量显示；只有收到 `done` 才表示完整历史已保存。`error` 或连接中断不视为成功。停止按钮中断客户端接收；模型服务端是否立即停止取决于连接释放时机，重新打开会话可确认最终保存状态。

消息使用 Vue 文本插值展示，不执行回复中的 HTML。当前版本面向本地单用户工作区。

## 工作区

“资源库”提供工作区列表、添加、设置和分页加载。添加时填写后端所在电脑上已存在的绝对目录；浏览器不提供本机绝对目录选择，因此使用路径输入框。默认只读且关闭终端；开启终端需要同时允许写入。终端使用当前 Windows 用户权限，可访问该用户有权限的其他目录。

输入框下方可选择工作区，或选择“不使用工作区”解绑。已有会话通过 `PUT /api/v1/sessions/{id}/workspace` 保存绑定；新建会话和首次发消息时传入 `workspace_id`。切换会话及刷新后以服务端保存的绑定为准，失败时保留原选择，发送期间禁止切换。

`src/api/client.js` 已接入工作区创建、分页列表、详情、设置及会话绑定接口；`useWorkspaces.js` 管理目录列表与详情，`useChat.js` 管理会话绑定。当前后端没有工作区删除接口，因此界面没有删除入口。

首次使用前，需在 `agent-base` 根目录运行 `.\.venv\Scripts\python.exe -B scripts\init_db.py`，创建工作区表及会话关联字段。前端测试使用内存请求替身，不访问真实数据库或模型。

## 界面

使用参考 HTML 中的 Rhizome 标志，提供亚克力白与炭黑两种主题。右上角切换主题；`Ctrl + K` 搜索会话；输入框外按 `N` 新建任务。工作台通过现有会话 API 判断连接，不依赖 `/health`。
