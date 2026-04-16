# Phase 3: CLI + Server — P3-S01 ~ P3-S04

Click CLI, FastAPI server, MCP client — 对外接口层。

---

## P3-S01: cli/main.py — Click CLI Scaffold `[ ]`

**Files:**
- `src/metiscode/cli/main.py`
- `src/metiscode/cli/__init__.py`
- `src/metiscode/__main__.py`
- `tests/cli/test_cli.py`

**Dependencies:** P2-S30

**TS Reference:** `opencode/packages/opencode/src/cli/` directory

**Work:**
- `src/metiscode/__main__.py`: `from metiscode.cli.main import cli; cli()` — 支持 `python -m metiscode`
- Click group `cli`:
  - `run` command:
    - `--model` option (default from config)
    - `--agent` option (default "build")
    - `--session-id` option (resume session)
    - positional `prompt` argument
    - 初始化 config, project context, session → 运行 SessionPrompt.prompt() → 打印 streaming output
  - `serve` command:
    - `--port` option (default 4096)
    - `--host` option (default "127.0.0.1")
    - 启动 uvicorn with FastAPI app
  - `session` group:
    - `list` — 列出当前 project 的 sessions
    - `show <id>` — 显示 session 详情
    - `delete <id>` — 删除 session
  - `tui` command:
    - 启动 Textual app (Phase 4 实现, 此处先 placeholder)

**Test Plan (3 tests):**
1. `cli --help` 输出包含 "run", "serve", "session", "tui"
2. `cli run --model anthropic:claude-sonnet-4-20250514 "hello"` 解析 model 参数正确
3. `cli session list` 空数据库 → 输出空列表

---

## P3-S02: server/app.py — FastAPI App + REST Routes `[ ]`

**Files:**
- `src/metiscode/server/app.py`
- `src/metiscode/server/routes.py`
- `src/metiscode/server/__init__.py`
- `tests/server/test_routes.py`

**Dependencies:** P2-S30, P2-S01

**TS Reference:** `opencode/packages/opencode/src/server/router.ts`, `server/routes/`

**Work:**
- FastAPI app with CORS middleware (allow all origins for dev)
- Routes:
  - `GET /session` → list sessions (paginated)
  - `GET /session/{id}` → get session with message count
  - `POST /session` → create new session (body: `{model?, agent?}`)
  - `POST /session/{id}/message` → send message (body: `{content: str}`)
  - `GET /session/{id}/messages` → get messages with parts (paginated)
  - `DELETE /session/{id}` → delete session
  - `GET /events` → SSE stream (Phase 3-S03)
  - `GET /ws` → WebSocket (Phase 3-S03)
  - `GET /health` → `{"status": "ok"}`
- 使用 `uvicorn` 启动

**Test Plan (4 tests, 使用 FastAPI TestClient):**
1. `GET /session` → 200, 空列表
2. `POST /session` → 201, 返回 session id
3. `GET /health` → 200, `{"status": "ok"}`
4. `POST /session/{id}/message` body 缺少 content → 422 validation error

---

## P3-S03: server/sse.py + server/ws.py — SSE + WebSocket Streaming `[ ]`

**Files:**
- `src/metiscode/server/sse.py`
- `src/metiscode/server/ws.py`
- `tests/server/test_sse.py`

**Dependencies:** P3-S02, P2-S03

**TS Reference:** `opencode/packages/opencode/src/server/event.ts`

**Work:**
- SSE endpoint (`GET /events`):
  - 订阅 EventBus
  - `text/event-stream` 格式: `data: {json}\n\n`
  - 包含 keepalive ping
  - Session filter (query param `?session_id=xxx`)
- WebSocket endpoint (`GET /ws`):
  - Bidirectional: server → client (bus events), client → server (commands)
  - Commands: `{type: "permission_reply", request_id, action}`, `{type: "abort", session_id}`
  - Permission reply 路由到 PermissionService.reply()

**Test Plan (3 tests):**
1. SSE: 发布 bus event → SSE 客户端接收到对应 JSON
2. WebSocket: 连接后接收 bus events
3. WebSocket: 发送 permission_reply → PermissionService 收到 reply

---

## P3-S04: mcp/client.py — MCP Client `[ ]`

**Files:**
- `src/metiscode/mcp/client.py`
- `src/metiscode/mcp/__init__.py`
- `tests/mcp/test_client.py`

**Dependencies:** P1-S06

**TS Reference:** `opencode/packages/opencode/src/mcp/index.ts`

**Work:**
- 使用 `mcp` Python 包 (official MCP SDK)
- `McpClient`:
  - `from_config(mcp_config: McpConfig) -> McpClient`
  - `async connect()` — 连接所有配置的 MCP servers
  - `async discover_tools() -> list[ToolInfo]` — 获取 MCP servers 提供的工具列表
  - `async execute_tool(server_name: str, tool_name: str, params: dict) -> str` — 代理执行
  - `async disconnect()` — 断开所有连接
- MCP server 连接类型:
  - stdio: `command` + `args` (launch subprocess)
  - SSE: `url` (connect to HTTP SSE endpoint)
- 将发现的工具注册到 ToolRegistry (作为 MCP 代理工具)

**Test Plan (2 tests):**
1. mock stdio MCP server → `discover_tools()` 返回工具列表
2. mock tool execution → 正确传递 params 并返回结果
