# Phase 5: Polish — P5-S01 ~ P5-S03

Skills, integration tests, final lint — 收尾工作。

---

## P5-S01: skill/loader.py — JSON Skill Loader `[ ]`

**Files:**
- `src/metiscode/skill/loader.py`
- `src/metiscode/skill/__init__.py`
- `tests/skill/test_loader.py`

**Dependencies:** P2-S24

**TS Reference:** `opencode/packages/opencode/src/skill/` directory

**Work:**
- Skill JSON format:
  ```json
  {
    "name": "commit",
    "description": "Create a git commit with good message",
    "system_prompt": "You are helping the user create a git commit...",
    "tools": ["bash", "read", "glob", "grep"]
  }
  ```
- `SkillInfo` dataclass: `name, description, system_prompt, tools: list[str]`
- `SkillLoader`:
  - 搜索路径:
    1. `{project_dir}/.metiscode/skills/*.json`
    2. `~/.metiscode/skills/*.json`
  - `load_all() -> dict[str, SkillInfo]` — 加载所有 skill 文件
  - `get(name: str) -> SkillInfo | None`
- 集成到 SkillTool (P2-S24): 查找到 skill 后, 注入 system_prompt 到当前会话

**Test Plan (3 tests):**
1. 加载有效 skill JSON → SkillInfo 字段正确
2. 搜索路径中无文件 → `load_all()` 返回空 dict
3. SkillTool 执行: 找到 skill 后, system_prompt 被注入到对话上下文

---

## P5-S02: Integration Tests — End-to-End Flows `[ ]`

**Files:**
- `tests/integration/__init__.py`
- `tests/integration/test_e2e.py`
- `tests/integration/test_session_lifecycle.py`

**Dependencies:** All previous slices

**TS Reference:** N/A

**Work:**
使用 mock LLM responses 进行端到端测试, 覆盖 AGENTS.md §10 验收检查:

**Test Plan (6 tests):**

1. **Basic Chat Flow** (验收 #4):
   - mock Anthropic stream: TextDelta → StepFinish
   - SessionPrompt.prompt("Hello") → 产生 text response
   - DB 中有 user message + assistant message + text part

2. **Tool Execution: Read + Edit** (验收 #5, #6):
   - mock stream: ToolInputEnd(tool="write") → ToolResult → StepFinish
   - 文件在磁盘上被创建
   - mock stream: ToolInputEnd(tool="edit") → ToolResult → StepFinish
   - 文件内容被正确修改

3. **Session Persistence** (验收 #11):
   - 创建 session, 发送 message, 关闭
   - 重新 load session → messages 完整
   - parts 数据完整

4. **Permission Blocking** (验收 #10):
   - 配置 `bash.run:rm *` 为 "deny"
   - mock stream: ToolInputEnd(tool="bash", input={"command": "rm -rf /"})
   - → DeniedError, 工具不执行

5. **Subagent Spawning** (验收 #9):
   - mock stream: ToolInputEnd(tool="task", input={"prompt": "...", "subagent_type": "general"})
   - 子 session 被创建, parent_id 正确
   - 子 session 的 agent 为 "general"

6. **Compaction Trigger** (验收相关):
   - 设置 context_limit=1000 的 mock model
   - 发送大量 messages 超过阈值
   - processor 返回 "compact" → compaction 执行
   - 旧 tool outputs 被标记为 compacted

---

## P5-S03: Final Polish — Type Check + Lint + Documentation `[ ]`

**Files:** Various

**Dependencies:** All previous slices

**Work:**
- 添加 `src/metiscode/py.typed` marker (PEP 561)
- 运行 `mypy src/metiscode` → 修复所有 type errors
- 运行 `ruff check src tests` → 修复所有 lint errors
- 运行 `ruff format src tests` → 格式化
- 每个包的 `__init__.py` 添加模块级 docstring
- 确保所有 public functions/methods 有 type hints

**Test Plan:**
1. `ruff check src tests` → 0 errors, exit code 0
2. `mypy src/metiscode` → 0 errors, exit code 0
3. `pytest -q` → all tests green
4. `python -c "import metiscode; print(metiscode.__version__)"` → 输出 "0.1.0"
