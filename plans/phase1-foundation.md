# Phase 1: Foundation — P1-S01 ~ P1-S09

scaffold, util, config, project, permission — 整个项目的基础层。

---

## P1-S01: Project Scaffold `[ ]`

**Files to create:**
- `pyproject.toml`
- `src/metiscode/__init__.py`
- 所有 15 个子包的 `__init__.py`: cli/, agent/, session/, tool/, provider/, llm/, permission/, config/, bus/, mcp/, project/, server/, tui/, skill/, util/
- `tests/__init__.py`, `tests/conftest.py`

**Dependencies:** None

**TS Reference:** N/A

**Work:**
- 创建 `pyproject.toml`:
  - `[project]` metadata (name="metiscode", version="0.1.0", python=">=3.12")
  - `[project.dependencies]`: click, textual, fastapi, uvicorn, pydantic>=2, structlog, httpx, websockets, mcp, watchdog, python-ulid, aiofiles, anthropic, openai
  - `[project.optional-dependencies] dev`: ruff, mypy, pytest, pytest-asyncio, pytest-cov, httpx (test client)
  - `[tool.ruff]` line-length=100
  - `[tool.mypy]` strict=true (or reasonable defaults)
  - `[project.scripts]` metiscode = "metiscode.cli.main:cli"
- 创建所有空 `__init__.py`
- `tests/conftest.py` 含共享 fixtures (tmp_path, event_loop)

**Test Plan:**
1. `pip install -e ".[dev]"` 安装成功
2. `ruff check src tests` 0 errors
3. `python -c "import metiscode"` 成功
4. `pytest --co` 收集 0 tests 但退出码 0

---

## P1-S02: util/errors.py — Custom Error Hierarchy `[ ]`

**Files:** `src/metiscode/util/errors.py`, `tests/util/test_errors.py`

**Dependencies:** P1-S01

**TS Reference:** `opencode/packages/opencode/src/util/error.ts`

**Work:**
- `MetiscodeError(Exception)` — 项目基类
- `NamedError(MetiscodeError)` — 含 `name: str` property (默认 = class name)
- Subclasses:
  - `NotFoundError` — 资源未找到
  - `AuthError` — 认证/授权失败
  - `ValidationError` — 输入校验失败
  - `AbortedError` — 操作被用户中止
  - `ContextOverflowError` — 上下文窗口溢出
  - `APIError(status_code: int, is_retryable: bool, response_body: str | None)` — LLM API 错误
- 每个类含 `to_dict() -> dict`

**Test Plan (4 tests):**
1. 实例化 MetiscodeError 并验证 message
2. `to_dict()` 往返: 包含 name, message 字段
3. `isinstance(APIError(...), MetiscodeError)` 为 True
4. `NamedError.name` 默认等于 `"NamedError"`; `APIError.name` 等于 `"APIError"`

---

## P1-S03: util/ids.py — ULID Generation `[ ]`

**Files:** `src/metiscode/util/ids.py`, `tests/util/test_ids.py`

**Dependencies:** P1-S01

**TS Reference:** `opencode/packages/opencode/src/id/id.ts`

**Work:**
- 使用 `python-ulid` 包
- ID 类型 (thin wrappers, 实际都返回 str):
  - `SessionId.make(value: str | None = None) -> str`
  - `MessageId.make(...) -> str`
  - `PartId.make(...) -> str`
  - `PermissionId.make(...) -> str`
- `make()` 无参时生成新 ULID; 有参时透传
- `new_ulid() -> str` 便捷函数

**Test Plan (3 tests):**
1. `SessionId.make()` 返回 26 字符 ULID 字符串
2. `SessionId.make("01ARZ3NDEKTSV4RRFFQ69G5FAV")` 返回原值
3. 两次 `new_ulid()` 调用结果单调递增 (按字典序)

---

## P1-S04: util/log.py — Structured Logging `[ ]`

**Files:** `src/metiscode/util/log.py`, `tests/util/test_log.py`

**Dependencies:** P1-S01

**TS Reference:** `opencode/packages/opencode/src/util/log.ts`

**Work:**
- `configure_logging(dev: bool = False)` — dev 模式用 ConsoleRenderer, 生产用 JSONRenderer
- `get_logger(name: str) -> structlog.BoundLogger`
- API key redaction processor: 正则匹配 `sk-[a-zA-Z0-9]{20,}` 替换为 `sk-***`
- 在 `structlog.configure()` 的 processors 链中添加 redaction

**Test Plan (3 tests):**
1. `get_logger("test")` 返回可用 logger, 可 `.info("msg")`
2. 包含 `sk-abc123...` 的 log 输出中 key 被替换为 `sk-***`
3. `logger.bind(user="alice").info("hi")` — 输出包含 `user=alice`

---

## P1-S05: config/schema.py — Pydantic Config Schemas `[ ]`

**Files:** `src/metiscode/config/schema.py`, `tests/config/test_schema.py`

**Dependencies:** P1-S02

**TS Reference:** `opencode/packages/opencode/src/config/config.ts` — the `Info` schema

**Work:**
Pydantic v2 models, 全部 `model_config = ConfigDict(extra="forbid")`:

- `PermissionRule` — `Literal["allow", "deny", "ask"]`
- `PermissionConfig` — `dict[str, PermissionRule | dict[str, PermissionRule]]`
- `ProviderConfig(name: str, api_key_env: str | None, base_url: str | None, models: dict)`
- `AgentConfig(model: str | None, prompt: str | None, permission: PermissionConfig | None, ...)`
- `McpServerConfig(command: str | None, args: list[str], env: dict, url: str | None)`
- `McpConfig` — `dict[str, McpServerConfig]`
- `CompactionConfig(threshold: int = 80000, ...)`
- `MetiscodeConfig` — top-level, 聚合以上所有:
  - `provider: dict[str, ProviderConfig]`
  - `agent: dict[str, AgentConfig]`
  - `permission: PermissionConfig`
  - `mcp: McpConfig`
  - `compaction: CompactionConfig`
  - `instructions: list[str]`
  - `default_model: str`
  - `theme: str`

**Test Plan (5 tests):**
1. 有效完整配置 JSON → `MetiscodeConfig` 解析成功
2. extra field → `ValidationError`
3. `permission: {"bash": "allow"}` 字符串形式解析
4. `permission: {"bash": {"run:git *": "allow"}}` dict 形式解析
5. 嵌套 `agent: {"build": {"model": "anthropic:claude-sonnet-4-20250514"}}` 解析

---

## P1-S06: config/loader.py — JSONC Loading + Hierarchy Merge `[ ]`

**Files:** `src/metiscode/config/loader.py`, `src/metiscode/config/__init__.py`, `tests/config/test_loader.py`

**Dependencies:** P1-S05, P1-S04

**TS Reference:** `opencode/packages/opencode/src/config/config.ts` — `read()`, `mergeConfigConcatArrays()`

**Work:**
- `strip_jsonc_comments(text: str) -> str` — 去除 `//` 行注释和 `/* */` 块注释
- `deep_merge(base: dict, override: dict) -> dict` — 深度合并, `instructions` 字段 concatenate 而非覆盖
- `load_config(project_dir: Path | None = None) -> MetiscodeConfig`:
  1. 加载 system defaults
  2. 加载 `~/.metiscode/config.jsonc` (global)
  3. 加载 `{project_dir}/.metiscode/config.jsonc` (project)
  4. 读取 `METISCODE_*` env vars 并覆盖
  5. 合并后验证为 `MetiscodeConfig`
- `ConfigService` class 持有当前配置的单例引用

**Test Plan (6 tests):**
1. `strip_jsonc_comments()` 正确去除 `//` 和 `/* */`
2. 单文件加载: 只有 global config 时正确解析
3. 层次合并: project config 的 `default_model` 覆盖 global
4. `METISCODE_DEFAULT_MODEL=openai:gpt-4.1` env var 覆盖
5. 全部文件缺失时返回默认 `MetiscodeConfig`
6. 无效 JSON 抛出包含文件路径的 `ValidationError`

---

## P1-S07: project/context.py — Directory & Project Context `[ ]`

**Files:** `src/metiscode/project/context.py`, `src/metiscode/project/__init__.py`, `tests/project/test_context.py`

**Dependencies:** P1-S06, P1-S03

**TS Reference:** `opencode/packages/opencode/src/project/instance.ts`, `project.ts`

**Work:**
- `ProjectContext` dataclass:
  - `directory: Path` — 工作目录
  - `worktree: Path` — git root 或 directory
  - `project_id: str` — ULID, 基于 directory 稳定生成
  - `is_git: bool`
- `detect_git_root(path: Path) -> Path | None` — `git rev-parse --show-toplevel`
- `ProjectContext.from_directory(path: Path | None = None) -> ProjectContext`
- 路径在内部统一用 `/` 分隔 (即使 Windows)

**Test Plan (4 tests):**
1. 在 git repo 中: `worktree` 等于 git root
2. 非 git 目录: `worktree` 等于 `directory`, `is_git=False`
3. 同一 directory 两次调用: `project_id` 相同
4. Windows 路径中的 `\` 被转换为 `/`

---

## P1-S08: permission/wildcard.py + evaluate.py — Core Permission Logic `[ ]`

**Files:**
- `src/metiscode/permission/wildcard.py`
- `src/metiscode/permission/evaluate.py`
- `src/metiscode/permission/__init__.py`
- `tests/permission/test_wildcard.py`
- `tests/permission/test_evaluate.py`

**Dependencies:** P1-S02

**TS Reference:** `opencode/packages/opencode/src/util/wildcard.ts`, `permission/evaluate.ts`

**Work:**
- `Wildcard.match(pattern: str, input: str) -> bool`:
  - 规范化: `\` → `/`
  - `*` 匹配任意字符序列 (不跨 `/`)
  - `**` 匹配跨 `/` 的任意序列
  - 尾部 ` *` (空格+星号) 匹配可选的后续参数
  - 整个 pattern 锚定为完整匹配
- `evaluate(permission: str, *rulesets: Ruleset) -> Literal["allow", "deny", "ask"]`:
  - `Ruleset = dict[str, Literal["allow", "deny", "ask"]]`
  - 遍历所有 rulesets (后面的优先级高), 找最后一个匹配的规则
  - 无匹配时返回 `"ask"`

**CRITICAL: 必须精确移植 TS 行为，移植全部 TS 测试用例**

**Test Plan (15+ tests):**
- `wildcard.test.ts` 全部用例移植:
  1. 精确匹配 `"foo"` matches `"foo"`
  2. `"foo*"` matches `"foobar"`
  3. `"bash.run:git *"` matches `"bash.run:git push origin main"`
  4. `"bash.run:git *"` does NOT match `"bash.run:npm install"`
  5. `"**/*.ts"` matches `"src/foo/bar.ts"`
  6. 空 pattern 不匹配任何非空 input
  7. 尾部空格+星号 optional 匹配
  8. Windows 反斜杠规范化
  9. Case sensitivity (默认区分大小写)
  10. 多个 `*` 在同一 pattern
- evaluate tests:
  11. 空 rulesets → `"ask"`
  12. 单 ruleset 含 `"deny"` → `"deny"`
  13. 两个 rulesets, 后者覆盖前者
  14. Wildcard pattern in ruleset key
  15. 无匹配 pattern → `"ask"`

---

## P1-S09: permission/service.py — PermissionService `[ ]`

**Files:** `src/metiscode/permission/service.py`, `tests/permission/test_service.py`

**Dependencies:** P1-S08, P1-S05

**TS Reference:** `opencode/packages/opencode/src/permission/index.ts`

**Work:**
- `Ruleset = dict[str, Literal["allow", "deny", "ask"]]`
- Exception classes:
  - `RejectedError(MetiscodeError)` — 用户拒绝
  - `CorrectedError(MetiscodeError, correction: str)` — 用户修改了输入
  - `DeniedError(MetiscodeError)` — 规则禁止
- `PermissionService`:
  - `from_config(config: PermissionConfig) -> Ruleset` — 展平嵌套 dict
  - `merge(*rulesets: Ruleset) -> Ruleset` — 合并多个 rulesets
  - `disabled(tool_names: list[str], ruleset: Ruleset) -> set[str]` — 返回被 deny 的工具名
  - `async ask(permission: str, rulesets: list[Ruleset]) -> None`:
    - 先 evaluate; 如果 "allow" 直接返回; 如果 "deny" 抛出 DeniedError
    - 如果 "ask": 发布 bus event, 创建 `asyncio.Event`, 等待 reply
  - `reply(request_id: str, action: str, correction: str | None = None)`:
    - `"once"` / `"always"` → 解除 ask 的阻塞
    - `"reject"` → 设置 RejectedError 并唤醒
    - `"correct"` → 设置 CorrectedError 并唤醒

**Test Plan (5 tests):**
1. `from_config({"bash": "allow", "edit": {"*.py": "ask"}})` 展平正确
2. `merge(r1, r2)` 含重叠 key 时 r2 覆盖
3. `disabled(["bash", "edit"], ruleset)` 返回 deny 的工具名集合
4. `ask()` + 另一个 coroutine 调用 `reply(id, "once")` → ask 正常返回
5. `ask()` + `reply(id, "reject")` → ask 抛出 `RejectedError`
