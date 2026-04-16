# Phase 2: Core Loop — P2-S01 ~ P2-S31

db, message, bus, all tools, agent, llm, processor, prompt, compaction — 项目核心。

---

## P2-S01: session/db.py — SQLite Schema + CRUD `[ ]`

**Files:** `src/metiscode/session/db.py`, `tests/session/test_db.py`

**Dependencies:** P1-S03

**TS Reference:** `opencode/packages/opencode/src/session/session.sql.ts`

**Work:**
- 使用 `aiosqlite` 包装 (整个项目统一选择)
- Tables:
  - `session(id TEXT PK, project_id TEXT, parent_id TEXT, slug TEXT, directory TEXT, title TEXT, version INT DEFAULT 1, permission TEXT, time_created TEXT, time_updated TEXT)`
  - `message(id TEXT PK, session_id TEXT FK, role TEXT, time_created TEXT, data TEXT)`
  - `part(id TEXT PK, message_id TEXT FK, session_id TEXT FK, type TEXT, time_created TEXT, data TEXT)`
  - `todo(id TEXT PK, session_id TEXT FK, content TEXT, status TEXT, priority INT, time_created TEXT)`
  - `permission_request(id TEXT PK, session_id TEXT FK, tool TEXT, pattern TEXT, action TEXT, time_created TEXT)`
- Indexes on `session_id` columns
- CRUD async functions:
  - `create_session()`, `get_session()`, `list_sessions()`, `update_session()`
  - `create_message()`, `get_messages()`, `get_message_parts()`
  - `create_part()`, `update_part()`
  - `create_todo()`, `update_todo()`, `get_todos()`
- DB path: `~/.metiscode/data/{project_id}.db`

**Test Plan (6 tests):**
1. `create_session()` → `get_session()` 往返
2. `create_message()` 关联到 session
3. `create_part()` 关联到 message
4. `list_sessions(project_id)` 返回该 project 的 sessions
5. 删除 session 级联删除 messages 和 parts
6. `data` 列 JSON 往返 (存 dict, 取回 dict)

---

## P2-S02: session/message.py — Message/Part Type Definitions `[ ]`

**Files:** `src/metiscode/session/message.py`, `tests/session/test_message.py`

**Dependencies:** P2-S01, P1-S02, P1-S03

**TS Reference:** `opencode/packages/opencode/src/session/message-v2.ts`

**Work:**
Pydantic models for all Part types:

- `TextPart(type="text", content: str)`
- `ReasoningPart(type="reasoning", content: str)`
- `ToolPart(type="tool", tool_id: str, input: dict, state: ToolState, output: str | None, error: str | None, metadata: dict | None)`
  - `ToolState = Literal["pending", "running", "completed", "error"]`
- `StepStartPart(type="step_start", step: int)`
- `StepFinishPart(type="step_finish", step: int, reason: str)`
- `CompactionPart(type="compaction", summary: str)`
- `FilePart(type="file", path: str, operation: str)`
- `SubtaskPart(type="subtask", session_id: str, description: str)`

Discriminated union: `Part = Annotated[TextPart | ReasoningPart | ..., Field(discriminator="type")]`

Messages:
- `UserMessage(id: str, role="user", parts: list[Part], time_created: str)`
- `AssistantMessage(id: str, role="assistant", parts: list[Part], model: str, time_created: str, time_completed: str | None)`

Error factories:
- `from_error(e: Exception) -> Part` — 根据异常类型生成对应 Part

**Test Plan (5 tests):**
1. `TextPart` serialize → deserialize 往返
2. `ToolPart` state 从 "pending" → "running" → "completed" 更新
3. `Part` discriminated union: `{"type": "text", "content": "hi"}` 解析为 `TextPart`
4. `UserMessage` 含 optional parts 字段
5. `from_error(APIError(...))` 返回包含错误信息的 TextPart

---

## P2-S03: bus/ — Pub/Sub Event System `[ ]`

**Files:** `src/metiscode/bus/event.py`, `src/metiscode/bus/bus.py`, `src/metiscode/bus/__init__.py`, `tests/bus/test_bus.py`

**Dependencies:** P1-S04

**TS Reference:** `opencode/packages/opencode/src/bus/bus-event.ts`, `bus/index.ts`

**Work:**
- `EventDefinition[T]` — typed event descriptor with `type_name: str`, `schema: type[T]`
- `BusEvent.define(type_name: str, schema: type[T]) -> EventDefinition[T]`
- `EventBus`:
  - `publish(event_def: EventDefinition[T], payload: T)` — 广播到所有订阅者
  - `subscribe(event_def: EventDefinition[T], callback: Callable[[T], Awaitable[None]]) -> Callable[[], None]` — 返回 unsubscribe 函数
  - `subscribe_all(callback: Callable[[str, Any], Awaitable[None]]) -> Callable[[], None]`
  - 内部使用 `asyncio.Queue` per subscriber for backpressure

**Test Plan (4 tests):**
1. publish event → subscriber callback 被调用且 payload 正确
2. `subscribe_all` 接收所有类型的事件
3. unsubscribe 后不再接收事件
4. 多个 subscriber 各自收到同一事件的独立副本

---

## P2-S04: tool/tool.py — Tool.define() Factory `[ ]`

**Files:** `src/metiscode/tool/tool.py`, `tests/tool/test_tool_define.py`

**Dependencies:** P2-S02, P1-S09

**TS Reference:** `opencode/packages/opencode/src/tool/tool.ts`

**Work:**
- `ToolContext` dataclass:
  - `session_id: str`, `message_id: str`, `agent: str`
  - `abort: asyncio.Event`, `metadata: Callable[[dict], None]`
  - `ask: Callable[[str, list[str]], Awaitable[None]]` — permission check
- `ToolResult` dataclass:
  - `title: str`, `output: str`, `metadata: dict | None`, `attachments: list[dict] | None`
- `ToolInfo`:
  - `id: str`, `description: str`, `parameters: type[BaseModel]`
  - `init(agent: str | None) -> ToolInstance`
- `ToolInstance`:
  - `execute(params: dict, ctx: ToolContext) -> ToolResult`
- `define(tool_id, description, parameters, execute_fn) -> ToolInfo` factory:
  - Wraps execute with: Pydantic validation → call → truncation

**Test Plan (4 tests):**
1. define 一个 echo tool, 调用返回正确 output
2. 传入不符合 schema 的 params → ValidationError
3. 超长 output 被 truncate
4. execute 中调用 `ctx.metadata({"key": "val"})` → metadata 记录

---

## P2-S05: tool/truncate.py — Output Truncation `[ ]`

**Files:** `src/metiscode/tool/truncate.py`, `tests/tool/test_truncate.py`

**Dependencies:** P1-S07

**TS Reference:** `opencode/packages/opencode/src/tool/truncate.ts`

**Work:**
- `TruncateResult(truncated: bool, output: str, overflow_path: str | None)`
- `truncate_output(text: str, max_chars: int = 80000) -> TruncateResult`:
  - 短文本: 直接返回
  - 长文本: 截断到 max_chars, 溢出部分写入 `~/.metiscode/tmp/{ulid}.txt`, 返回截断文本 + 提示信息 + 文件路径

**Test Plan (3 tests):**
1. 短文本 (100 chars): truncated=False, output 不变
2. 长文本 (200K chars): truncated=True, output 被截断, 末尾含提示
3. 溢出文件写入正确路径且内容完整

---

## P2-S06: tool/registry.py — Tool Registry `[ ]`

**Files:** `src/metiscode/tool/registry.py`, `tests/tool/test_registry.py`

**Dependencies:** P2-S04

**TS Reference:** `opencode/packages/opencode/src/tool/registry.ts`

**Work:**
- `ToolRegistry`:
  - `_tools: dict[str, ToolInfo]`
  - `register(tool: ToolInfo)` — 注册工具
  - `ids() -> list[str]` — 返回所有已注册工具 ID
  - `get(tool_id: str) -> ToolInfo | None`
  - `get_tools(agent: str, model: str | None = None) -> list[ToolInstance]`:
    - 过滤: agent mode (primary/subagent/all), model capabilities
    - 初始化并返回 ToolInstance 列表

**Test Plan (3 tests):**
1. register → get 往返
2. `ids()` 返回所有注册名称 (排序)
3. `get_tools(agent="general")` 不包含 subagent-only 工具

---

## P2-S07: tool/bash.py — Bash Tool `[ ]`

**Files:** `src/metiscode/tool/bash.py`, `tests/tool/test_bash.py`

**Dependencies:** P2-S04, P1-S09

**TS Reference:** `opencode/packages/opencode/src/tool/bash.ts`

**Work:**
- Parameters schema: `command: str, timeout: int = 120000, description: str | None = None`
- Permission: `ask(permission="bash.run:{command_prefix}", ...)`
- Execution:
  - Windows: 检测命令类型, 简单命令用 `cmd.exe /c`, 复杂命令用 PowerShell
  - `asyncio.create_subprocess_exec` or `asyncio.create_subprocess_shell`
  - stdout + stderr 合并捕获
  - timeout 强制 kill
- 返回: exit code + stdout/stderr

**Test Plan (5 tests):**
1. `echo hello` → output 包含 "hello"
2. timeout=100 + `sleep 10` → timeout error
3. permission `ask` 被调用, pattern 包含命令前缀
4. stderr 输出被捕获并包含在 output 中
5. Windows 路由: `dir` 走 cmd.exe, `Get-Process` 走 PowerShell

---

## P2-S08: tool/read.py — Read Tool `[ ]`

**Files:** `src/metiscode/tool/read.py`, `tests/tool/test_read.py`

**Dependencies:** P2-S04, P1-S09

**TS Reference:** `opencode/packages/opencode/src/tool/read.ts`

**Work:**
- Parameters: `file_path: str, offset: int | None = None, limit: int | None = None`
- 行号格式输出: `{line_number}\t{content}`
- offset/limit 切片
- 二进制文件检测 (前 8192 bytes 含 null byte → 报告为二进制)
- `.env`, `.env.local` 等文件: permission check
- 文件不存在: 清晰错误信息

**Test Plan (4 tests):**
1. 读取文本文件, 输出包含行号
2. offset=5, limit=3 → 只返回第 5-7 行
3. 二进制文件 → 返回 "binary file" 提示
4. `.env` 文件 → permission ask 被调用

---

## P2-S09: tool/write.py — Write Tool `[ ]`

**Files:** `src/metiscode/tool/write.py`, `tests/tool/test_write.py`

**Dependencies:** P2-S04, P1-S09

**TS Reference:** `opencode/packages/opencode/src/tool/write.ts`

**Work:**
- Parameters: `file_path: str, content: str`
- 自动创建父目录 (`Path.mkdir(parents=True, exist_ok=True)`)
- Permission: `ask(permission="write:{relative_path}", ...)`
- 如果文件已存在: 生成 diff 作为 output
- 如果文件为新: output 包含 "created" 信息

**Test Plan (3 tests):**
1. 写入新文件 → 文件存在且内容正确
2. 深层路径 `a/b/c/d.txt` → 父目录自动创建
3. permission ask 被调用, 包含相对路径

---

## P2-S10: tool/edit.py — Core + SimpleReplacer + MultiOccurrenceReplacer `[ ]`

**Files:** `src/metiscode/tool/edit.py`, `tests/tool/test_edit_simple.py`

**Dependencies:** P2-S04, P1-S09

**TS Reference:** `opencode/packages/opencode/src/tool/edit.ts` — lines 1-60, 196-199, 496-508, 630-667

**Work:**
- 行尾工具函数:
  - `detect_line_ending(text: str) -> str` — 检测 `\r\n` / `\n` / `\r`
  - `normalize_line_endings(text: str) -> str` — 统一为 `\n`
  - `convert_to_line_ending(text: str, ending: str) -> str`
- `Replacer` Protocol: `def __call__(search: str, content: str) -> Generator[str, None, None]` — yield 候选匹配的原始文本
- `SimpleReplacer` — 精确匹配, yield `search` 本身 (在 content 中寻找)
- `MultiOccurrenceReplacer` — 精确匹配所有出现位置, 各自 yield
- `replace(content: str, old_string: str, new_string: str, replace_all: bool = False) -> str`:
  - 按顺序尝试所有 Replacer (Simple → LineTrimmed → ... → ContextAware)
  - 找到 match 后执行替换
  - 错误处理: old==new, not found, multiple matches without replace_all
- `EditTool` definition: parameters `file_path`, `old_string`, `new_string`, `replace_all`

**Test Plan (5 tests):**
1. 精确匹配: `replace("hello world", "hello", "hi")` → `"hi world"`
2. `replace_all=True` 替换所有出现
3. `old_string == new_string` → raise error
4. 未找到 old_string → raise error
5. 多处匹配 + `replace_all=False` → raise error (ambiguous)

---

## P2-S11: tool/edit.py — LineTrimmedReplacer `[ ]`

**Files:** `src/metiscode/tool/edit.py` (追加), `tests/tool/test_edit_linetrimmed.py`

**Dependencies:** P2-S10

**TS Reference:** `src/tool/edit.ts` lines 200-238

**Work:**
- `LineTrimmedReplacer`: 按行 trim 后比较
  - 将 search 按行 split, 每行 strip
  - 在 content 中找到每行 strip 后匹配的连续行块
  - yield 原始 (未 strip) 的文本范围

**Test Plan (4 tests):**
1. search 有前导空格, content 有不同前导空格 → 匹配
2. search 有尾部空格 → 匹配
3. 多行 search + content 各行缩进不同 → 匹配
4. 内容实际不同 (不只是空白差异) → 不匹配

---

## P2-S12: tool/edit.py — BlockAnchorReplacer `[ ]`

**Files:** `src/metiscode/tool/edit.py` (追加), `tests/tool/test_edit_blockanchor.py`

**Dependencies:** P2-S10

**TS Reference:** `src/tool/edit.ts` lines 240-373

**Work:**
- `levenshtein_distance(a: str, b: str) -> int` — 编辑距离
- `levenshtein_ratio(a: str, b: str) -> float` — 归一化相似度 (0.0 = 完全不同, 1.0 = 相同)
- `BlockAnchorReplacer`:
  - search 至少 3 行
  - 首行 = anchor: 在 content 中找所有 Levenshtein ratio ≥ 0.7 的行
  - 从每个 anchor 开始取等长 block
  - 单候选: 阈值 0.0 (几乎总是匹配)
  - 多候选: 阈值 0.3, 选最高相似度
  - 计算中间行的平均 Levenshtein ratio 作为分数

**Test Plan (5 tests):**
1. 单候选匹配 — 首行精确, 中间行略有差异
2. 多候选 — 选择相似度最高的 block
3. search < 3 行 → 不产生候选 (返回空)
4. 首行无匹配 → 不产生候选
5. `levenshtein_distance("kitten", "sitting")` = 3

---

## P2-S13: tool/edit.py — WhitespaceNormalizedReplacer `[ ]`

**Files:** `src/metiscode/tool/edit.py` (追加), `tests/tool/test_edit_whitespace.py`

**Dependencies:** P2-S10

**TS Reference:** `src/tool/edit.ts` lines 375-417

**Work:**
- `WhitespaceNormalizedReplacer`:
  - 规范化: 将连续空白 (spaces, tabs) 压缩为单个空格
  - 单行匹配: 规范化 search 和 content 的每行, 找到匹配
  - 多行匹配: 整块规范化后比较

**Test Plan (4 tests):**
1. search `"foo  bar"` 匹配 content `"foo bar"` (多余空格)
2. search 含 tab, content 含空格 → 匹配
3. 多行 search, 各行空白不同 → 匹配
4. 行内子串匹配 (search 是行的一部分)

---

## P2-S14: tool/edit.py — IndentationFlexibleReplacer `[ ]`

**Files:** `src/metiscode/tool/edit.py` (追加), `tests/tool/test_edit_indent.py`

**Dependencies:** P2-S10

**TS Reference:** `src/tool/edit.ts` lines 419-445

**Work:**
- `IndentationFlexibleReplacer`:
  - 去除 search 和 content 各块的最小缩进 (common indent)
  - 比较去缩进后的内容
  - 匹配时 yield 原始文本范围

**Test Plan (3 tests):**
1. search 缩进 4 spaces, content 缩进 8 spaces → 匹配
2. search 用 tab, content 用 spaces (混合) → 匹配
3. 去缩进后内容不同 → 不匹配

---

## P2-S15: tool/edit.py — EscapeNormalizedReplacer `[ ]`

**Files:** `src/metiscode/tool/edit.py` (追加), `tests/tool/test_edit_escape.py`

**Dependencies:** P2-S10

**TS Reference:** `src/tool/edit.ts` lines 447-494

**Work:**
- `EscapeNormalizedReplacer`:
  - 反转义处理: `\\n` → `\n`, `\\t` → `\t`, `\\r` → `\r`, `\\'` → `'`, `\\"` → `"`, `` \\` `` → `` ` ``, `\\\\` → `\\`, `\\$` → `$`
  - 行延续: `\` + newline → 空字符串
  - 先对 search 反转义, 再在 content 中查找

**Test Plan (3 tests):**
1. search `"hello\\nworld"` 匹配 content `"hello\nworld"` (literal newline)
2. search `"it\\'s"` 匹配 content `"it's"`
3. 多行 search 含转义 → 匹配 content 中的实际字符

---

## P2-S16: tool/edit.py — TrimmedBoundaryReplacer + ContextAwareReplacer `[ ]`

**Files:** `src/metiscode/tool/edit.py` (追加), `tests/tool/test_edit_remaining.py`

**Dependencies:** P2-S10

**TS Reference:** `src/tool/edit.ts` lines 510-592

**Work:**
- `TrimmedBoundaryReplacer`:
  - strip search 的首尾空行
  - 在 content 中查找 stripped 版本
  - 如果 stripped == 原始 search (无变化) → 不 yield (避免与 SimpleReplacer 重复)
- `ContextAwareReplacer`:
  - search 至少 3 行
  - 首行和末行作为 anchor (需精确匹配)
  - content 中找同样首尾行的 block
  - 仅考虑与 search 等长的 blocks
  - 计算中间行的 Levenshtein ratio, 阈值 0.5 (50%)
  - 单候选直接匹配, 多候选选最高分

**Test Plan (5 tests):**
1. TrimmedBoundary: search 有前导空行 → 匹配
2. TrimmedBoundary: search 无多余空白 → 不 yield
3. ContextAware: 首尾行精确匹配, 中间行相似 → 匹配
4. ContextAware: 中间行相似度 < 50% → 不匹配
5. ContextAware: search < 3 行 → 不 yield

---

## P2-S17: tool/edit.py — Full Replacer Chain Integration `[ ]`

**Files:** `tests/tool/test_edit_integration.py`

**Dependencies:** P2-S10 ~ P2-S16

**TS Reference:** `opencode/test/tool/edit.test.ts`

**Work:**
- **移植 TS 测试用例**
- 测试完整 `replace()` 函数的回退链行为
- 测试辅助函数: `trim_diff()`

**Test Plan (6 tests):**
1. Simple 失败 → LineTrimmed 成功 (空白差异)
2. 所有策略回退到 ContextAware 最终匹配
3. `replace_all=True` 使用第一个找到匹配的策略
4. 行尾检测: `\r\n` 文件中替换后保持 `\r\n`
5. `old_string=""` (空字符串) + 新文件创建
6. `trim_diff()` 去除 diff 输出的公共缩进

---

## P2-S18: tool/glob.py — Glob Tool `[ ]`

**Files:** `src/metiscode/tool/glob.py`, `tests/tool/test_glob.py`

**Dependencies:** P2-S04

**TS Reference:** `opencode/packages/opencode/src/tool/glob.ts`

**Work:**
- Parameters: `pattern: str, path: str | None = None`
- 使用 `pathlib.Path.glob()` 或 `glob.glob(recursive=True)`
- 排序: 按修改时间降序
- 忽略 `.git`, `node_modules`, `__pycache__` 等

**Test Plan (3 tests):**
1. `"*.py"` 匹配当前目录的 .py 文件
2. `"**/*.py"` 递归匹配
3. 无匹配 → 返回空列表

---

## P2-S19: tool/grep.py — Grep Tool `[ ]`

**Files:** `src/metiscode/tool/grep.py`, `tests/tool/test_grep.py`

**Dependencies:** P2-S04

**TS Reference:** `opencode/packages/opencode/src/tool/grep.ts`

**Work:**
- Parameters: `pattern: str, path: str | None, include: str | None, context: int = 2`
- 优先使用 `rg` (ripgrep) subprocess; 不可用时回退到 Python `re` + 文件遍历
- 输出格式: `{file}:{line}:{content}`

**Test Plan (3 tests):**
1. 正则匹配: `"def \\w+"` 找到函数定义
2. `include="*.py"` 只搜索 .py 文件
3. context=2 显示上下文行

---

## P2-S20: tool/websearch.py — WebSearch Tool `[ ]`

**Files:** `src/metiscode/tool/websearch.py`, `tests/tool/test_websearch.py`

**Dependencies:** P2-S04

**TS Reference:** `opencode/packages/opencode/src/tool/websearch.ts`

**Work:**
- Parameters: `query: str, num_results: int = 5`
- 使用 httpx 调用搜索 API (可配置 endpoint)
- 格式化结果: title, url, snippet

**Test Plan (2 tests):**
1. mock HTTP response → 正确解析为搜索结果列表
2. 空结果 → 返回 "no results" 信息

---

## P2-S21: tool/webfetch.py — WebFetch Tool `[ ]`

**Files:** `src/metiscode/tool/webfetch.py`, `tests/tool/test_webfetch.py`

**Dependencies:** P2-S04

**TS Reference:** `opencode/packages/opencode/src/tool/webfetch.ts`

**Work:**
- Parameters: `url: str, prompt: str | None = None`
- httpx GET, HTML → markdown (简单实现: strip tags + 保留结构)
- 15 分钟缓存 (dict + timestamp)
- redirect 处理

**Test Plan (3 tests):**
1. mock HTML → 转换为可读 markdown
2. 重复请求同一 URL → 缓存命中 (无网络调用)
3. redirect → 返回最终 URL 信息

---

## P2-S22: tool/todo.py — TodoWrite Tool `[ ]`

**Files:** `src/metiscode/tool/todo.py`, `tests/tool/test_todo.py`

**Dependencies:** P2-S04, P2-S01

**TS Reference:** `opencode/packages/opencode/src/tool/todo.ts`, `session/todo.ts`

**Work:**
- Parameters: `todos: list[TodoItem]` where `TodoItem = {content: str, status: Literal["pending", "in_progress", "done"], priority: int}`
- 写入 SQLite todo table
- 返回格式化的 todo 列表

**Test Plan (2 tests):**
1. 创建 3 个 todos → DB 中有 3 行
2. 更新 todo status → DB 中状态变更

---

## P2-S23: tool/question.py + tool/plan.py — Question & Plan Tools `[ ]`

**Files:** `src/metiscode/tool/question.py`, `src/metiscode/tool/plan.py`, `tests/tool/test_question.py`

**Dependencies:** P2-S04, P1-S09

**TS Reference:** `opencode/packages/opencode/src/tool/question.ts`, `tool/plan.ts`

**Work:**
- QuestionTool:
  - Parameters: `question: str, options: list[str] | None`
  - 通过 permission 系统的 ask 流程向用户提问
  - 返回用户的回答
- PlanTool (plan_exit):
  - Parameters: none
  - 信号: 退出 plan mode

**Test Plan (2 tests):**
1. QuestionTool 调用 `ctx.ask()` 并返回回答
2. PlanTool 设置 plan_exit 标志

---

## P2-S24: tool/skill.py — Skill Tool (Stub) `[ ]`

**Files:** `src/metiscode/tool/skill.py`, `tests/tool/test_skill.py`

**Dependencies:** P2-S04

**TS Reference:** `opencode/packages/opencode/src/tool/skill.ts`

**Work:**
- Parameters: `skill_name: str, args: str | None`
- V1 stub: 查找已注册的 skill 定义, 注入 system prompt
- 未找到 → 返回 "skill not found" 信息
- 完整实现在 P5-S01

**Test Plan (1 test):**
1. 初始化无错误, 未注册 skill 时返回 "not found"

---

## P2-S25: tool/task.py — Subagent Spawning `[ ]`

**Files:** `src/metiscode/tool/task.py`, `tests/tool/test_task.py`

**Dependencies:** P2-S04, P2-S01, P2-S02, P1-S09

**TS Reference:** `opencode/packages/opencode/src/tool/task.ts`

**Work:**
- Parameters: `description: str, prompt: str, subagent_type: str | None, task_id: str | None`
- 新建子 session (parent_id = 当前 session)
- 根据 subagent_type 选择 agent (默认 "general")
- 运行 prompt → 收集最终文本结果
- 如果 task_id 存在: 恢复已有子 session

**Test Plan (3 tests):**
1. mock session 创建 → 子 session 的 parent_id 正确
2. permission check: subagent agent 的 permission 被应用
3. 传入 task_id → 恢复已有 session 而非新建

---

## P2-S26: agent/agent.py — AgentService + Built-in Agents `[ ]`

**Files:** `src/metiscode/agent/agent.py`, `src/metiscode/agent/__init__.py`, `tests/agent/test_agent.py`

**Dependencies:** P1-S05, P1-S06, P1-S09, P2-S05

**TS Reference:** `opencode/packages/opencode/src/agent/agent.ts`

**Work:**
- `AgentInfo` Pydantic model:
  - `name: str`, `description: str`
  - `mode: Literal["primary", "subagent", "all"]`
  - `permission: Ruleset` — default permission rules
  - `model: str | None` — override model
  - `prompt: str | None` — additional system prompt
  - `tools: list[str] | None` — tool whitelist/blacklist
  - `max_steps: int = 50`
  - `temperature: float | None`, `top_p: float | None`
- Built-in agents:
  - `build` (primary, default, 全部工具, 标准权限)
  - `plan` (primary, 拒绝 edit 除 plans/ 目录)
  - `general` (subagent, 无 todowrite)
  - `explore` (subagent, read-only: 只有 read/glob/grep/webfetch/websearch)
  - `compaction` (hidden, 无工具, 用于 LLM 摘要)
  - `title` (hidden, 无工具, 用于生成 session 标题)
  - `summary` (hidden, 无工具, 用于生成摘要)
- `AgentService`:
  - `get(name: str) -> AgentInfo`
  - `list() -> list[AgentInfo]` (排除 hidden)
  - `default_agent() -> AgentInfo` (返回 "build")
  - 合并用户 config 覆盖

**Test Plan (5 tests):**
1. `get("build")` 有正确的 permission ruleset
2. `get("plan")` 的 permission 拒绝 `edit:*` 但允许 `edit:plans/*`
3. 用户 config 含 `agent.build.model = "openai:gpt-4.1"` → 合并后 model 被覆盖
4. `default_agent()` 返回 name="build"
5. `list()` 不包含 hidden agents (compaction, title, summary)

---

## P2-S27: llm/stream.py — StreamEvent Taxonomy + LLMService `[ ]`

**Files:** `src/metiscode/llm/stream.py`, `src/metiscode/llm/__init__.py`, `tests/llm/test_stream.py`

**Dependencies:** P2-S02, P2-S26, P1-S06

**TS Reference:** `opencode/packages/opencode/src/session/llm.ts`

**CRITICAL: StreamEvent 分类法不可简化**

**Work:**
StreamEvent dataclasses (discriminated union by `type` field):
- `Start(type="start", model: str)`
- `TextStart(type="text_start")`
- `TextDelta(type="text_delta", content: str)`
- `TextEnd(type="text_end")`
- `ReasoningStart(type="reasoning_start")`
- `ReasoningDelta(type="reasoning_delta", content: str)`
- `ReasoningEnd(type="reasoning_end")`
- `ToolInputStart(type="tool_input_start", tool_id: str, name: str)`
- `ToolInputDelta(type="tool_input_delta", content: str)`
- `ToolInputEnd(type="tool_input_end")`
- `StepStart(type="step_start")`
- `StepFinish(type="step_finish", reason: str)`
- `Finish(type="finish", usage: Usage)`
- `Error(type="error", error: Exception)`

`Usage` dataclass: `input_tokens: int, output_tokens: int, cache_read: int, cache_write: int`

`LLMService`:
- `stream(model: str, messages: list, tools: list, system: str, ...) -> AsyncGenerator[StreamEvent]`
- 内部 dispatch 到 provider-specific 实现:
  - `_stream_anthropic()` — `anthropic.AsyncAnthropic().messages.stream()`, 映射 `content_block_start/delta/stop`, `message_delta`, thinking blocks
  - `_stream_openai()` — `openai.AsyncOpenAI().chat.completions.create(stream=True)`, 映射 `choices[0].delta`, tool_calls 缓冲
  - `_stream_deepseek()` — OpenAI SDK + custom base_url, `reasoning_content` → ReasoningDelta
- JSON 缓冲: tool call arguments 分片到达时, 缓冲直到完整再 yield ToolInputEnd

**Test Plan (5 tests):**
1. mock Anthropic stream → 产生正确的 StreamEvent 序列 (Start → TextStart → TextDelta... → Finish)
2. mock OpenAI stream with tool_calls → ToolInputStart + ToolInputDelta + ToolInputEnd 序列
3. mock DeepSeek stream with `reasoning_content` → ReasoningDelta 事件
4. partial JSON 缓冲: 分两次 delta 到达的 tool arguments → 最终合并为完整 JSON
5. API 错误 → Error event

---

## P2-S28: provider/provider.py — ProviderService `[ ]`

**Files:** `src/metiscode/provider/provider.py`, `src/metiscode/provider/__init__.py`, `tests/provider/test_provider.py`

**Dependencies:** P1-S06, P1-S02

**TS Reference:** `opencode/packages/opencode/src/provider/provider.ts`

**Work:**
- `ProviderInfo(id: str, name: str, api_key_env: str, base_url: str | None)`
- `ModelInfo(id: str, provider_id: str, name: str, context_limit: int, output_limit: int, supports_reasoning: bool, supports_images: bool, supports_temperature: bool)`
- Built-in providers + models:
  - `anthropic`: claude-sonnet-4-20250514 (200K ctx), claude-opus-4-20250514, claude-haiku-3.5
  - `openai`: gpt-4.1, gpt-4.1-mini, o3, o4-mini
  - `deepseek`: deepseek-chat, deepseek-reasoner (supports_reasoning=True)
- `ProviderService`:
  - `parse_model(model_str: str) -> tuple[str, str]` — `"anthropic:claude-sonnet-4-20250514"` → `("anthropic", "claude-sonnet-4-20250514")`
  - `get_provider(provider_id: str) -> ProviderInfo`
  - `get_model(provider_id: str, model_id: str) -> ModelInfo`
  - `default_model() -> tuple[ProviderInfo, ModelInfo]` — 从 config 读取

**Test Plan (4 tests):**
1. `parse_model("anthropic:claude-sonnet-4-20250514")` → ("anthropic", "claude-sonnet-4-20250514")
2. `get_model("anthropic", "claude-sonnet-4-20250514")` → ModelInfo with context_limit=200000
3. `default_model()` 使用 config 中的 `default_model`
4. `get_provider("unknown")` → raise NotFoundError

---

## P2-S29: session/processor.py — Main Loop State Machine `[ ]`

**Files:** `src/metiscode/session/processor.py`, `tests/session/test_processor.py`

**Dependencies:** P2-S27, P2-S02, P2-S01, P2-S03, P1-S09

**TS Reference:** `opencode/packages/opencode/src/session/processor.ts`

**Work:**
- `SessionProcessor`:
  - `create(session_id, assistant_message, model, agent, abort) -> SessionProcessor`
  - `async process(stream_input: StreamInput) -> Literal["continue", "compact", "stop"]`:
    - 遍历 `LLMService.stream()` 的 StreamEvent
    - `TextDelta` → 更新/创建 TextPart in DB
    - `ReasoningDelta` → 更新/创建 ReasoningPart
    - `ToolInputEnd` → 创建 ToolPart (state="pending"), 执行工具, 更新为 "completed"/"error"
    - `StepFinish` → 检查是否需要继续 (有 tool_use → "continue")
    - `Finish` → "stop" (无 tool_use) 或 "continue" (有 tool_use)
    - `Error` → 检查是否可重试; ContextOverflow → "compact"
  - Doom loop 检测: 连续 3 次相同 tool call (同 tool_id + 同 input) → 自动停止
  - 发布 bus events: `part.created`, `part.updated`, `message.completed`

**Test Plan (4 tests):**
1. mock stream 含 TextDelta → DB 中创建 TextPart
2. mock stream 含 ToolInputEnd → ToolPart 生命周期 (pending → running → completed)
3. mock stream 含 Error(retryable) → 返回 "continue" (重试)
4. mock stream 含 Error(ContextOverflow) → 返回 "compact"

---

## P2-S30: session/prompt.py — System Prompts + Message Assembly `[ ]`

**Files:** `src/metiscode/session/prompt.py`, `tests/session/test_prompt.py`

**Dependencies:** P2-S29, P2-S26, P2-S06, P2-S02

**TS Reference:** `opencode/packages/opencode/src/session/prompt.ts`

**Work:**
- `build_system_prompt(agent: AgentInfo, project: ProjectContext, config: MetiscodeConfig) -> str`:
  - 基础 system prompt (角色, 能力, 限制)
  - + agent-specific prompt
  - + project instructions (from config + CLAUDE.md)
  - + 当前 todos (如果有)
  - + 时间戳
- `to_model_messages(messages: list[Message], model: str, provider: str) -> list[dict]`:
  - 转换内部 Message/Part 到 provider SDK 格式
  - Anthropic: `{"role": "assistant", "content": [{"type": "text", ...}, {"type": "tool_use", ...}]}`
  - OpenAI: `{"role": "assistant", "content": "...", "tool_calls": [...]}`
  - TextPart → text content
  - ToolPart (completed) → tool_use + tool_result
  - CompactionPart → user message with summary
- `SessionPrompt`:
  - `async prompt(input: str, session_id: str | None = None) -> AsyncGenerator[StreamEvent]`:
    - 主入口: 创建 user message, 创建 assistant message, 组装 messages, 调 processor.process()
    - 循环: process → "continue" → 再调 process; "compact" → 执行 compaction → 再调 process; "stop" → 结束

**Test Plan (4 tests):**
1. system prompt 包含 agent prompt 文本
2. `to_model_messages`: TextPart → `{"type": "text", "text": "..."}`
3. `to_model_messages`: ToolPart → tool_use + tool_result 对
4. CompactionPart → 转为 user role 的 text message

---

## P2-S31: session/compaction.py — Context Pruning `[ ]`

**Files:** `src/metiscode/session/compaction.py`, `tests/session/test_compaction.py`

**Dependencies:** P2-S29, P2-S02, P2-S01

**TS Reference:** `opencode/packages/opencode/src/session/compaction.ts`

**Work:**
V1 简化版 (不做 LLM 摘要, 仅截断):
- Constants: `PRUNE_MINIMUM = 20000`, `PRUNE_PROTECT = 40000`
- `is_overflow(total_tokens: int, model: ModelInfo) -> bool`:
  - `total_tokens > model.context_limit * 0.8`
- `async prune(session_id: str, model: ModelInfo)`:
  - 加载所有 messages + parts
  - 保护: system message + 最近 PRUNE_PROTECT tokens 的 messages
  - 从最旧开始: 将 ToolPart 的 output 替换为 `"[compacted]"`
  - 直到 total estimated tokens < PRUNE_MINIMUM
  - 插入 CompactionPart 标记

**Test Plan (3 tests):**
1. `is_overflow(180000, model_200k)` → True
2. prune: 旧 ToolPart output 被标记为 compacted
3. prune: 近期 ToolPart 不被影响 (在 PRUNE_PROTECT 范围内)
