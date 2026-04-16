# Port OpenCode to Python (metiscode)

## Context

OpenCode is a production-grade AI coding agent (MIT licensed, ~14K lines core TypeScript) with agent system, 15+ tools, multi-provider LLM support, SQLite persistence, full TUI, and HTTP server. The goal is to port it to Python and simplify appropriately -- removing enterprise/cloud features, the Effect framework overhead, and complex optional subsystems.

User confirmed:

- Full TUI with themes, keyboard shortcuts, dialogs
- Providers: Anthropic, OpenAI, deepseek
- MCP client included
- Project name: **metiscode**

## What to Port vs. Drop

### Port (core)

- Agent system (build/plan/general) with permission rulesets
- Tool registry: bash, read, write, edit, glob, grep, task (subagent), websearch, webfetch, todo, skill, question, plan
- Provider system: Anthropic, OpenAI, deepseek
- Session management: SQLite, message history, forking, compaction
- Permission system: wildcard rules (allow/deny/ask)
- CLI: run, serve, session commands
- Config: JSON loading with hierarchy, Pydantic schemas
- LLM streaming: text, reasoning, tool calls
- MCP client (connecting to external servers)
- Full TUI: themes, keyboard shortcuts, session list, permission dialogs

### Simplify/Skip

| Feature                   | Decision                                 |
| ------------------------- | ---------------------------------------- |
| Solid.js TUI              | Rewrite in Python Textual                |
| Hono server               | Rewrite in FastAPI                       |
| Drizzle ORM               | Replace with raw sqlite3                 |
| Effect framework          | Drop - use async/await + service classes |
| TypeScript plugin loading | Drop - Python dict-based hooks           |
| LSP integration           | Skip v1                                  |
| Snapshot/undo system      | Skip v1                                  |
| Multi-workspace           | Single-project only                      |
| mDNS discovery            | Skip                                     |
| Share/collaboration       | Skip v1                                  |
| Account/cloud features    | Skip                                     |
| JSON migration            | Skip (fresh SQLite)                      |
| Auto-update               | Skip                                     |
| MCP server                | Keep MCP client only                     |
| Enterprise/ACPs           | Skip                                     |
| Markdown skills           | Simplify to JSON-based                   |
| GPT apply_patch tool      | Skip                                     |

## Project Structure

```
metiscode/
├── pyproject.toml
├── src/metiscode/
│   ├── __init__.py
│   ├── cli/          # Click CLI (run, serve, session)
│   ├── agent/        # Agent definitions (build, plan, general)
│   ├── session/      # Session, messages, processor, compaction, db
│   ├── tool/         # All tools (bash, read, write, edit, glob, grep, etc.)
│   ├── provider/     # Anthropic, OpenAI, deepseek
│   ├── config/       # Config loading + Pydantic schemas
│   ├── permission/   # Wildcard permission evaluation
│   ├── llm/          # Streaming interface
│   ├── bus/          # Pub/sub event bus
│   ├── mcp/          # MCP client
│   ├── project/      # Directory/project context
│   ├── server/       # FastAPI app + routes
│   ├── tui/          # Textual TUI app
│   ├── skill/        # Skill loader
│   └── util/         # Logging, IDs, errors
└── tests/
```

## Tech Stack

| Subsystem     | Library                         |
| ------------- | ------------------------------- |
| Runtime       | Python 3.12+ (uv)               |
| AI SDK        | anthropic, openai (Python SDKs) |
| CLI           | Click                           |
| TUI           | Textual                         |
| Server        | FastAPI + uvicorn               |
| Database      | sqlite3 (stdlib)                |
| Schema        | Pydantic v2                     |
| File watching | watchdog                        |
| Logging       | structlog                       |
| HTTP          | httpx                           |
| WebSocket     | websockets                      |
| MCP           | mcp Python package              |

## Key Design Decisions

### 1. Effect -> Service Classes

Replace Effect framework with plain async/await + constructor-injected service classes. Every Layer.effect(Service, Effect.gen(...)) becomes a Python class with async def methods. No framework overhead.

### 2. Branded Types -> Pydantic + type aliases

```python
class SessionId:
    value: str
    @classmethod
    def make(cls, id: str | None = None) -> SessionId:
        return cls(value=id or ulid())
```

### 3. AI Providers -> Direct Python SDKs

LLMService wraps provider-specific SDKs:

```python
class LLMService:
    async def stream(self, model: str, messages: list[dict], tools: list[Tool]) -> AsyncGenerator[StreamEvent]:
        # dispatches to Anthropic/OpenAI/
```

StreamEvent union: text_start, text_delta, tool_call, tool_result, reasoning_delta, step_start, step_finish, error.

### 4. Tool Definition Pattern

```python
def define_tool(tool_id: str, init_fn: Callable):
    async def execute(params: dict, ctx: ToolContext) -> ToolResult:
        # Pydantic validation + execution + truncation
        return result
    return ToolInfo(id=tool_id, execute=execute)
```

Parameter schemas via Pydantic BaseModels.

### 5. Edit Tool -- Keep All Strategies

The TypeScript edit.ts has 9 string replacement strategies (simple, line-trimmed, block-anchor, whitespace-normalized, etc.) -- critical for agent functionality. Port directly.

### 6. Config Hierarchy

Load and deep-merge from: system config -> global config -> project config -> env vars. Strip // and /\* \*/ comments from JSONC.

## Critical TypeScript Source Files (port in order)

1. src/config/config.ts -- ConfigService foundation
2. src/session/processor.ts -- Heart: streaming state machine, tool calls, reasoning, steps
3. src/session/message-v2.ts -- Message/part type definitions + DB persistence
4. src/tool/edit.ts -- Most complex tool (9 replacer strategies, 667 lines)
5. src/provider/provider.ts -- Provider abstraction pattern
6. src/session/prompt.ts -- System prompt building, message assembly
7. src/agent/agent.ts -- Built-in agent definitions with permission rulesets
8. src/tool/bash.ts -- Command parsing, arity resolution
9. src/permission/index.ts -- Wildcard permission evaluation
10. src/tool/registry.ts -- Tool registry and discovery
11. src/session/compaction.ts -- Context overflow pruning + summarization
12. src/tool/task.ts -- Subagent spawning

## Implementation Phases

### Phase 1: Foundation

1. Project scaffold (pyproject.toml, ruff config, directory structure)
2. util/ -- logging, ID generation (ULID), custom errors
3. config/ -- Pydantic schemas + config loading service
4. project/ -- Directory context, project info
5. permission/ -- Wildcard evaluation, PermissionService
6. provider/ -- ProviderService (Anthropic, OpenAI, deepseek)

### Phase 2: Core Loop

7. session/db.py -- SQLite schema + CRUD
8. session/message.py -- Message/part types
9. bus/ -- Pub/sub event system
10. tool/tool.py -- Tool.define() factory
11. tool/registry.py -- ToolRegistry service
12. All tools: bash, read, write, edit, glob, grep, task, websearch, webfetch, todo, skill, question, plan
13. agent/ -- AgentService + built-in agents
14. llm/ -- Streaming interface + LLMService
15. session/processor.py -- Main loop state machine
16. session/prompt.py -- System prompts + message assembly
17. session/compaction.py -- Context pruning

### Phase 3: CLI + Server

18. cli/ -- Click commands (run, serve, session)
19. server/ -- FastAPI app + REST routes + SSE + WebSocket
20. mcp/ -- MCP client service

### Phase 4: TUI

21. tui/ -- Textual app, prompt input, message display, dialogs

### Phase 5: Polish

22. skill/ -- JSON-based skill loader
23. Integration tests

## Verification

1. ruff check src/ -- no lint errors
2. python -m metiscode run "Hello world" -- basic chat works
3. python -m metiscode run "Create a hello.py file" -- file creation works
4. python -m metiscode run "Edit hello.py to add a function" -- edit tool works
5. python -m metiscode serve + curl session endpoints -- server responds
6. python -m metiscode tui -- TUI renders and accepts input
7. Spawn subagent with task tool -- nested session works
8. Permission prompts appear for restricted operations
9. Session history persists across restarts (SQLite)
10. Multiple providers work (switch between anthropic/openai/)
