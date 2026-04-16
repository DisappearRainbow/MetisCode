# metiscode Slice Plan / 切片开发规划

## Overview / 总览

本目录包含 metiscode 项目的详细切片开发规划。将 OpenCode (TypeScript) 到 Python 的移植工作分解为 **52 个最小切片**，每个切片对应一次 Codex 编码 turn。

## Workflow / 工作流程

- **Claude Code**: 规划、研究、审查、更新规划状态
- **Codex**: 编码实现（每个切片一次 turn，`suggest` mode）
- 每个切片完成后: `ruff check` + `mypy` + `pytest` → `git commit`

## Slice Naming Convention / 切片命名规则

格式: `P{phase}-S{sequence}` (e.g., `P1-S01`, `P2-S17`)

- **P1**: Foundation (脚手架, util, config, project, permission)
- **P2**: Core Loop (db, message, bus, tools, agent, llm, processor)
- **P3**: CLI + Server (Click, FastAPI, MCP)
- **P4**: TUI (Textual app, widgets, dialogs)
- **P5**: Polish (skills, integration tests)

## Slice Status Legend / 状态标记

| Symbol | Meaning |
|--------|---------|
| `[ ]` | todo — 未开始 |
| `[~]` | in_progress — 进行中 |
| `[x]` | done — 已完成 |
| `[-]` | skipped — 跳过 |

## Files / 文件列表

| File | Content | Slices |
|------|---------|--------|
| [phase1-foundation.md](phase1-foundation.md) | Foundation: scaffold, util, config, project, permission | P1-S01 ~ P1-S09 (9) |
| [phase2-core-loop.md](phase2-core-loop.md) | Core Loop: db, message, bus, tools, agent, llm, processor | P2-S01 ~ P2-S31 (31) |
| [phase3-cli-server.md](phase3-cli-server.md) | CLI + Server: Click, FastAPI, MCP | P3-S01 ~ P3-S04 (4) |
| [phase4-tui.md](phase4-tui.md) | TUI: Textual app, widgets, dialogs, themes | P4-S01 ~ P4-S05 (5) |
| [phase5-polish.md](phase5-polish.md) | Polish: skills, integration tests, lint | P5-S01 ~ P5-S03 (3) |
| [dependency-graph.md](dependency-graph.md) | Dependency graph / 依赖关系图 | — |

## Quick Stats / 快速统计

| Phase | Slices | Test Count (est.) |
|-------|--------|-------------------|
| 1 | 9 | ~37 |
| 2 | 31 | ~110 |
| 3 | 4 | ~12 |
| 4 | 5 | ~9 |
| 5 | 3 | ~12 |
| **Total** | **52** | **~180** |

## Environment Reminder / 环境提醒

```
$PY = "C:/Users/18742/.conda/envs/llm_learn/python.exe"
& $PY -m pip install -e ".[dev]"    # install
& $PY -m ruff check src tests       # lint
& $PY -m mypy src/metiscode         # type check
& $PY -m pytest -q                  # test
```

## Acceptance Criteria / 验收标准

见 AGENTS.md §10，共 12 项验收检查。全部通过 = v1 完成。
