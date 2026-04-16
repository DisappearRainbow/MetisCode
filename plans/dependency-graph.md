# Dependency Graph / 依赖关系图

## Legend / 图例

- `→` = depends on / 依赖
- 同一行的切片可以并行执行
- **Critical path** / 关键路径: 标记为 **bold**

---

## Phase 1: Foundation

```
P1-S01 (scaffold)
  ├→ P1-S02 (errors)
  ├→ P1-S03 (ids)
  └→ P1-S04 (log)

P1-S02 → P1-S05 (config/schema)
P1-S05 + P1-S04 → P1-S06 (config/loader)
P1-S06 + P1-S03 → P1-S07 (project/context)

P1-S02 → P1-S08 (permission/wildcard+evaluate)
P1-S08 + P1-S05 → P1-S09 (permission/service)
```

### Phase 1 并行可能性:

| Step | 可并行切片 | 前置条件 |
|------|-----------|---------|
| 1 | P1-S01 | — |
| 2 | P1-S02, P1-S03, P1-S04 | P1-S01 |
| 3 | P1-S05, P1-S08 | P1-S02 |
| 4 | P1-S06 | P1-S05, P1-S04 |
| 5 | P1-S07, P1-S09 | P1-S06+P1-S03, P1-S08+P1-S05 |

---

## Phase 2: Core Loop

```
P1-S03 → P2-S01 (session/db)
P2-S01 + P1-S02 + P1-S03 → P2-S02 (session/message)
P1-S04 → P2-S03 (bus)
P2-S02 + P1-S09 → P2-S04 (tool/tool.py)
P1-S07 → P2-S05 (tool/truncate)
P2-S04 → P2-S06 (tool/registry)

# Tools (大部分依赖 P2-S04, 可并行):
P2-S04 + P1-S09 → P2-S07 (bash)
P2-S04 + P1-S09 → P2-S08 (read)
P2-S04 + P1-S09 → P2-S09 (write)
P2-S04 + P1-S09 → P2-S10 (edit core)
P2-S04 → P2-S18 (glob)
P2-S04 → P2-S19 (grep)
P2-S04 → P2-S20 (websearch)
P2-S04 → P2-S21 (webfetch)
P2-S04 + P2-S01 → P2-S22 (todo)
P2-S04 + P1-S09 → P2-S23 (question+plan)
P2-S04 → P2-S24 (skill stub)
P2-S04 + P2-S01 + P2-S02 + P1-S09 → P2-S25 (task)

# Edit replacers (严格顺序):
P2-S10 → P2-S11 → P2-S12 → P2-S13 → P2-S14 → P2-S15 → P2-S16 → P2-S17

# Agent + LLM + Processor (严格顺序):
P1-S05 + P1-S06 + P1-S09 + P2-S05 → P2-S26 (agent)
P2-S02 + P2-S26 + P1-S06 → P2-S27 (llm/stream)
P1-S06 + P1-S02 → P2-S28 (provider)
P2-S27 + P2-S02 + P2-S01 + P2-S03 + P1-S09 → P2-S29 (processor)
P2-S29 + P2-S26 + P2-S06 + P2-S02 → P2-S30 (prompt)
P2-S29 + P2-S02 + P2-S01 → P2-S31 (compaction)
```

### Phase 2 关键路径:

```
**P2-S01 → P2-S02 → P2-S04 → P2-S06**
                              → P2-S10 → ... → P2-S17 (edit chain)
**P2-S26 → P2-S27 → P2-S29 → P2-S30 → P2-S31**
```

### Phase 2 并行可能性:

| Step | 可并行切片 |
|------|-----------|
| 1 | P2-S01, P2-S03, P2-S05 |
| 2 | P2-S02, P2-S28 |
| 3 | P2-S04 |
| 4 | P2-S06, P2-S07, P2-S08, P2-S09, P2-S10, P2-S18~S24 |
| 5 | P2-S11, P2-S25, P2-S26 |
| 6 | P2-S12, P2-S27 |
| 7 | P2-S13, P2-S29 |
| 8 | P2-S14, P2-S30 |
| 9 | P2-S15, P2-S31 |
| 10 | P2-S16 |
| 11 | P2-S17 |

---

## Phase 3: CLI + Server

```
P2-S30 → P3-S01 (CLI)
P2-S30 + P2-S01 → P3-S02 (FastAPI)
P3-S02 + P2-S03 → P3-S03 (SSE+WS)
P1-S06 → P3-S04 (MCP) # 可提前到 Phase 2 后期
```

---

## Phase 4: TUI

```
P3-S01 → P4-S01 (app scaffold)
P4-S01 → P4-S02 (prompt input)
P4-S01 + P2-S02 → P4-S03 (messages)
P4-S01 + P1-S09 → P4-S04 (dialogs)
P4-S01 + P1-S06 → P4-S05 (themes)
```

### Phase 4 并行可能性:

| Step | 可并行切片 |
|------|-----------|
| 1 | P4-S01 |
| 2 | P4-S02, P4-S03, P4-S04, P4-S05 |

---

## Phase 5: Polish

```
P2-S24 → P5-S01 (skills)
All → P5-S02 (integration tests)
All → P5-S03 (final polish)
```

---

## Overall Critical Path / 总体关键路径

最长依赖链 (决定项目最短完成时间):

```
P1-S01 → P1-S02 → P1-S05 → P1-S06 → P2-S26 → P2-S27 → P2-S29 → P2-S30 → P3-S01 → P4-S01 → P4-S03 → P5-S02
```

**12 步** — 即使完美并行, 至少需要 12 个 sequential Codex turns 才能走通关键路径。

实际预计: 由于单 Codex 实例无法并行, 全部 52 个切片需要 52 个 turns。
