# AGENTS.md — metiscode

This file guides coding agents (Codex CLI, and other AGENTS.md-aware tools) working in this repository. **Read it fully before taking any action on the first turn of a session.**

---

## 1. Project overview

**metiscode** is a Python 3.12+ port (and deliberate simplification) of [OpenCode](https://github.com/anomalyco/opencode), a TypeScript AI coding agent. The TS source lives in `./opencode/` (reference only — never modify). Target layout lives in `./src/metiscode/`.

Goal: keep the core loop (agent + tools + permissions + streaming + SQLite sessions + TUI) and drop cloud/enterprise features (share, console, account, multi-workspace, LSP, snapshot, ACP, auto-update).

Full spec: see `PLAN.md` in repo root.

---

## 2. Environment — IMPORTANT

**All Python commands MUST use the `llm_learn` conda environment:**

```
C:/Users/18742/.conda/envs/llm_learn/python.exe
```

Rules:
- **Never** run bare `python`, `py`, `python3`, or `pip` — always use the full path above, or `conda run -n llm_learn <cmd>`.
- **Never** create a venv, install to user site, or call `uv`/`poetry` to bootstrap a different environment.
- For package installs: `C:/Users/18742/.conda/envs/llm_learn/python.exe -m pip install <pkg>` — and ask the user first if a new dependency is not yet in `pyproject.toml`.
- For running modules: `C:/Users/18742/.conda/envs/llm_learn/python.exe -m metiscode ...`
- For pytest: `C:/Users/18742/.conda/envs/llm_learn/python.exe -m pytest ...`

Platform is **Windows (native, not WSL)**. Do not assume POSIX. `bash` tool behaviour, subprocess calls, path separators, and line endings must account for this.

Suggested alias inside scripts (PowerShell): define `$PY = "C:/Users/18742/.conda/envs/llm_learn/python.exe"` and use `& $PY ...`.

---

## 3. Codex-specific operational notes

### 3.1 Approval & sandbox mode

Codex's Linux/macOS sandboxes do not apply here (native Windows). Recommended settings:

- **Approval mode**: `suggest` for first pass on any new module; `auto-edit` once the module has tests passing and you're iterating. Avoid `full-auto` while the core loop (`processor.py`, `edit.py`, `permission/`) is still being built — silent edits there are expensive to undo.
- **Sandbox**: accept that on native Windows Codex runs without its usual sandbox. Compensate by:
  1. Committing often (`git commit -am "wip: <slice>"` after each passing milestone) so rollback is cheap.
  2. Never running destructive shell commands (`rm`, `del /s`, `git reset --hard`, `git clean -fd`) without explicit user confirmation in the same turn.
  3. Never editing anything under `./opencode/` (see §4.1).

### 3.2 Recommended `~/.codex/config.toml`

If the user hasn't already configured Codex, these defaults fit this project:

```toml
model = "gpt-5-codex"          # or whatever the user prefers; this project is model-agnostic
approval_mode = "suggest"
# On Windows native there is no meaningful sandbox; keep approval tight instead.
```

Project-local overrides (if any) belong in `./.codex/config.toml`, not in this file.

### 3.3 Shell invocations

Codex's `shell` tool runs via `cmd.exe` on native Windows. Rules:
- Prefer PowerShell for anything nontrivial: `powershell -NoProfile -Command "..."`.
- Never pipe `|` across `cmd.exe` and assume POSIX semantics.
- For long commands, write a `.ps1` script under `scripts/` and invoke it, rather than cramming everything into one line.

### 3.4 Patches

When editing files, prefer **replacing whole functions or whole classes** in a single patch over many tiny edits. Codex's patch format handles block replacements cleanly. Exception: `edit.py`'s 9 replacer strategies should be implemented one strategy at a time with a test per strategy.

---

## 4. Directory layout

```
metiscode-v2/
├── opencode/                # TS reference source — READ ONLY, do not modify
├── src/metiscode/
│   ├── cli/                 # Click commands (run, serve, session, tui)
│   ├── agent/               # Built-in agents (build, plan, general)
│   ├── session/             # db, message, processor, prompt, compaction
│   ├── tool/                # bash, read, write, edit, glob, grep, task, websearch, webfetch, todo, skill, question, plan
│   ├── provider/            # Anthropic, OpenAI, DeepSeek
│   ├── llm/                 # Unified streaming interface + StreamEvent union
│   ├── permission/          # Wildcard rule evaluator + PermissionService
│   ├── config/              # Pydantic schemas + hierarchical JSONC loader
│   ├── bus/                 # Pub/sub event bus
│   ├── mcp/                 # MCP client (no server)
│   ├── project/             # Project/directory context
│   ├── server/              # FastAPI + SSE + WebSocket
│   ├── tui/                 # Textual app
│   ├── skill/               # JSON-based skill loader
│   └── util/                # logging, ids (ULID), errors
├── tests/
├── pyproject.toml
├── PLAN.md
└── AGENTS.md                # this file
```

Do not introduce top-level packages outside `src/metiscode/` without a good reason.

---

## 5. Porting discipline

### 5.1 Source of truth

When porting behaviour, **always locate the original TS file first** under `./opencode/packages/opencode/src/`. The critical files (in rough dependency order, which supersedes PLAN.md's "Critical TypeScript Source Files" list when they conflict):

1. `src/config/config.ts` — ConfigService
2. `src/session/message-v2.ts` — message/part types (port *before* processor)
3. `src/session/processor.ts` — streaming state machine (THE core)
4. `src/provider/provider.ts` — provider abstraction
5. `src/session/prompt.ts` — system prompt + message assembly
6. `src/agent/agent.ts` — built-in agents + permission rulesets
7. `src/tool/registry.ts` — tool registry
8. `src/tool/edit.ts` — 9 string-replace strategies (PORT ALL OF THEM)
9. `src/tool/bash.ts` — command parsing
10. `src/permission/index.ts` — wildcard permission evaluation
11. `src/session/compaction.ts` — context pruning (see simplification note below)
12. `src/tool/task.ts` — subagent spawning

### 5.2 Translation rules

- **Effect → plain async classes.** Every `Layer.effect(Service, Effect.gen(...))` becomes a Python class with `async def` methods and constructor-injected deps. No monadic plumbing, no `yield*`, no `Effect.runPromise`. Just `await`.
- **Branded types → Pydantic + `@classmethod make(...)`.** Don't invent a `NewType` chain; a small dataclass or Pydantic model with a `make()` classmethod is enough.
- **Zod → Pydantic v2.** Map schemas 1:1 where feasible. Tool parameter schemas are Pydantic `BaseModel`s.
- **Drizzle → stdlib `sqlite3`.** Raw SQL with parameterised queries. Schema lives in `session/db.py` as `CREATE TABLE IF NOT EXISTS ...`.
- **Hono → FastAPI.** Keep the same route shapes so the TUI and any future clients speak the same API.
- **`bun`/`node:fs` → `pathlib` + `aiofiles` where async matters.**
- **AI SDK → official `anthropic` / `openai` Python SDKs.** DeepSeek uses the `openai` SDK with a custom `base_url`.

### 5.3 Simplifications that are OK

- **Compaction v1**: just truncate oldest non-pinned messages once total tokens > threshold, keep system + last N turns + todo/task parts. Don't port the LLM-summarization path in v1. Leave a clear hook for it later.
- **Skills**: JSON-based loader only. Skip the markdown frontmatter parser in v1.
- **Plugin system**: drop entirely. Hooks can be a `dict[str, list[Callable]]` on the bus.

### 5.4 Do NOT simplify

- `edit.py`'s 9 replacer strategies. Port every one, including the tests. Simple-replace → line-trimmed → block-anchor → whitespace-normalised → indentation-flexible → etc. Name them identically to the TS implementation so a grep across both codebases lines up.
- The permission wildcard semantics. `bash.run:git *` must match `bash.run:git push origin main`. Write unit tests against the TS behaviour.
- The StreamEvent taxonomy: `text_start`, `text_delta`, `tool_call_start`, `tool_call_delta`, `tool_call_end`, `tool_result`, `reasoning_start`, `reasoning_delta`, `step_start`, `step_finish`, `error`. Providers must normalise into this union; reasoning deltas in particular differ between Anthropic (thinking blocks), OpenAI (o-series reasoning), and DeepSeek (`reasoning_content`).

---

## 6. Build, lint, test commands

Prefix everything with the pinned Python. Define once per session (PowerShell):

```powershell
$PY = "C:/Users/18742/.conda/envs/llm_learn/python.exe"
```

| Task | Command |
| --- | --- |
| Install project (editable) | `& $PY -m pip install -e ".[dev]"` |
| Lint | `& $PY -m ruff check src tests` |
| Format | `& $PY -m ruff format src tests` |
| Type check | `& $PY -m mypy src/metiscode` |
| Run all tests | `& $PY -m pytest -q` |
| Run one test file | `& $PY -m pytest tests/tool/test_edit.py -q` |
| Run CLI | `& $PY -m metiscode run "hello world"` |
| Start server | `& $PY -m metiscode serve --port 4096` |
| Launch TUI | `& $PY -m metiscode tui` |

Before marking any task complete, run **at minimum**: `ruff check`, `mypy`, and the relevant `pytest` subtree. Do not claim completion with failing checks.

---

## 7. Coding conventions

- **Python 3.12+ features allowed**: PEP 695 type params, `type` statements, `match`, `@override`.
- **Type hints are mandatory** on all public functions/methods. `Any` requires a comment explaining why.
- **Async by default** for anything that touches I/O, LLMs, or subprocesses. Never mix `asyncio` with `threading` without a clear boundary.
- **Pydantic v2** for all user-facing config and tool parameter schemas. Use `model_config = ConfigDict(extra="forbid")` on config schemas.
- **`dataclasses(slots=True, frozen=True)`** is fine for internal value objects where Pydantic is overkill.
- **IDs**: ULID strings via `util/ids.py`. Never `uuid4`.
- **Logging**: structlog, bound logger per module: `log = structlog.get_logger(__name__)`. Never `print` except in CLI output paths.
- **Errors**: subclass `metiscode.util.errors.MetiscodeError`. Never bare `Exception` in `except` unless re-raising.
- **Imports**: absolute within the package (`from metiscode.tool.edit import ...`). No `from . import *`.
- **Line length**: 100. Ruff config is the source of truth.

---

## 8. Workflow expectations

Codex runs best with small, verified steps. Follow this rhythm:

1. **Plan before you code.** For any task touching more than one file, produce a short plan in chat and wait for approval. State which source TS file you're porting from (cite path + line range), which Python module you'll create/edit, and which tests you'll add.
2. **One slice per turn.** A slice = one module + its tests passing. Don't chain "implement processor + compaction + task tool" into one turn; each is its own slice. **The full slice plan lives in `plans/`.** Each slice ID (e.g., `P1-S03`) corresponds to one coding turn. Before starting a slice, check its dependencies are done.
3. **Port in dependency order.** Don't start `processor.py` before `message.py` and `bus/` are usable. Don't start `compaction.py` before `processor.py` emits steps. See `plans/dependency-graph.md` for the full dependency graph.
4. **Write tests alongside.** For `edit.py` replacers and `permission/` wildcards, copy the TS test cases into `tests/` and translate them. These two modules are behavioural-compatibility critical.
5. **Run checks before declaring done.** Every slice ends with `ruff check`, `mypy`, and the relevant `pytest`. Paste the last lines of output so the user can confirm.
6. **Commit per slice.** `git add -A && git commit -m "feat(<area>): <slice>"` after each green slice. Rollback becomes cheap.
7. **Never touch `./opencode/`.** It's a read-only reference. If you need to experiment with the TS code, print the grep result and reason about it — do not modify.
8. **Secrets**: API keys come from (in order) env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`) then `~/.metiscode/auth.json`. Never log a key; redact to `sk-***` in any debug output.
9. **Ask, don't assume**, when a TS behaviour is ambiguous — show the user the relevant snippet and your two candidate translations.

---

## 9. Phase status — update as you go

Keep this table current. When starting a phase, mark it `in_progress`; when all its tests pass, mark `done`.

| Phase | Scope | Slices | Status | Current Slice |
| --- | --- | --- | --- | --- |
| 1 | scaffold, util, config, project, permission, provider | P1-S01~S09 | done | — |
| 2 | db, message, bus, tool registry, all tools, agent, llm, processor, prompt, compaction | P2-S01~S31 | done | — |
| 3 | CLI, FastAPI server, MCP client | P3-S01~S04 | done | — |
| 4 | Textual TUI (prompt input, message list, tool/diff render, permission dialog, session picker, themes, keybindings) | P4-S01~S05 | done | — |
| 5 | Skills (JSON), integration tests, polish | P5-S01~S03 | done | — |

Detailed slice plans with per-slice test plans: see `plans/` directory.

---

## 10. Acceptance checks (v1 done = all green)

Run in order; each must pass:

1. `ruff check src tests` — 0 errors
2. `mypy src/metiscode` — 0 errors
3. `pytest -q` — all green
4. `& $PY -m metiscode run "Hello world"` — basic streaming chat works against Anthropic
5. `& $PY -m metiscode run "Create hello.py that prints hi"` — `write` tool works, file appears on disk
6. `& $PY -m metiscode run "Edit hello.py to add a greet() function"` — `edit` tool succeeds with at least the simple + line-trimmed replacer
7. `& $PY -m metiscode serve` + `curl http://localhost:4096/session` — server responds 200
8. `& $PY -m metiscode tui` — Textual app launches, accepts input, streams reply
9. Ask the agent to spawn a subagent via the `task` tool — nested session stored in SQLite
10. Trigger a restricted bash command (e.g. `bash.run:rm *`) — permission dialog blocks it
11. Kill the process mid-session; restart; session history is intact (SQLite)
12. Switch provider mid-session (`/model openai:gpt-4.1`) — continues without losing context

---

## 11. Known traps

- **Windows shell tool**: on Windows, prefer `subprocess.run([...], shell=False)` with a real argv list. If the user's command is a shell one-liner, detect it and run via `cmd.exe /c` or PowerShell — never naive `shell=True` string concatenation.
- **Anthropic tool-use streaming**: `input_json_delta` events arrive as partial JSON strings; buffer until `content_block_stop` before parsing.
- **OpenAI tool streaming**: arguments arrive as fragmented strings on `choices[0].delta.tool_calls[i].function.arguments`; same buffering pattern, but index-keyed.
- **DeepSeek reasoning**: appears in `choices[0].delta.reasoning_content`, separate from `content`. Map to `reasoning_delta` events.
- **SQLite + asyncio**: stdlib `sqlite3` is sync. Either wrap calls in `asyncio.to_thread`, or use `aiosqlite`. Pick one and stick with it across `session/db.py`.
- **ULID on Windows**: prefer `python-ulid`; `ulid-py` has historically had issues with Windows wheels.
- **Textual on Windows**: works, but terminal rendering differs between Windows Terminal, ConEmu, and plain `cmd.exe`. Test in Windows Terminal.

---

## 12. Slice plan reference

The `plans/` directory contains the detailed slice-by-slice development plan:

- `plans/README.md` — overview + workflow + stats
- `plans/phase1-foundation.md` through `plans/phase5-polish.md` — per-phase slices with files, dependencies, TS references, work description, and test plans
- `plans/dependency-graph.md` — full dependency graph with parallelism analysis

Each slice file uses `[ ]` / `[~]` / `[x]` markers for status tracking. When starting a slice, update its marker to `[~]`; when done, to `[x]`.

---

## 13. When in doubt

- Behaviour question → read the TS source in `./opencode/`, cite the file:line when proposing the Python version.
- Architecture question → re-read `PLAN.md`, then this file's §5.
- Scope question → ask the user. Don't silently expand beyond the phase you're in.
