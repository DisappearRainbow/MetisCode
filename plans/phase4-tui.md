# Phase 4: TUI — P4-S01 ~ P4-S05

Textual TUI app — 完整的终端用户界面。

---

## P4-S01: tui/app.py — Textual App Scaffold `[ ]`

**Files:**
- `src/metiscode/tui/app.py`
- `src/metiscode/tui/__init__.py`
- `tests/tui/test_app.py`

**Dependencies:** P3-S01

**TS Reference:** N/A (Textual rewrite, 不移植 Solid.js TUI)

**Work:**
- Textual `App` subclass `MetiscodeApp`:
  - Layout: 3 区域
    - Header: app title + model indicator + session info
    - Body: message list (scrollable) — `MessageList` widget
    - Footer: input area + keybinding hints
  - CSS styling: 基础暗色主题
  - Bindings:
    - `ctrl+c` — quit
    - `ctrl+n` — new session
    - `ctrl+l` — clear screen
    - `ctrl+k` — command palette
  - Command palette: 切换 model, 切换 session, 切换 theme
- `MetiscodeApp.compose()` 返回 widget 树
- `MetiscodeApp.on_mount()` 初始化 config, project, session

**Test Plan (2 tests, 使用 Textual pilot):**
1. `app = MetiscodeApp()` 实例化无错误
2. Pilot: mount 后包含 MessageList, PromptInput, Footer widgets

---

## P4-S02: tui/prompt.py — Prompt Input Widget `[ ]`

**Files:** `src/metiscode/tui/prompt.py`, `tests/tui/test_prompt.py`

**Dependencies:** P4-S01

**TS Reference:** Console app prompt input (概念参考)

**Work:**
- `PromptInput(Widget)`:
  - 多行 TextArea
  - `Enter` 提交 (触发 `PromptSubmitted` event)
  - `Shift+Enter` 换行
  - `Up` 在空输入时回溯历史
  - `Down` 在历史中前进
  - Slash command 解析: `/model`, `/session`, `/clear`, `/help`, `/quit`
  - File drop/paste 支持 (将文件路径添加到消息)
- `PromptSubmitted` event: 包含 `content: str`, `files: list[str]`
- History 存储: 内存 list (最近 100 条)

**Test Plan (2 tests, Textual pilot):**
1. 输入文本 + 模拟 Enter → `PromptSubmitted` event 触发, content 正确
2. 输入后 Up arrow → 显示上一条历史

---

## P4-S03: tui/messages.py — Message Display Widget `[ ]`

**Files:** `src/metiscode/tui/messages.py`, `tests/tui/test_messages.py`

**Dependencies:** P4-S01, P2-S02

**TS Reference:** Console app message rendering (概念参考)

**Work:**
- `MessageList(ScrollableContainer)`:
  - 渲染 UserMessage 和 AssistantMessage
  - 支持 streaming: 实时追加 TextDelta
- `UserMessageWidget(Static)`:
  - 显示用户输入, 简洁样式
- `AssistantMessageWidget(Widget)`:
  - Markdown 渲染 (Textual 的 `Markdown` widget)
  - TextPart → markdown 内容
  - ReasoningPart → collapsible 区域 (默认折叠)
  - ToolPart → collapsible 区域: tool name + state indicator
    - "pending" → spinner
    - "running" → spinner + 已有输出
    - "completed" → checkmark + 可展开输出
    - "error" → X mark + 错误信息
  - FilePart → diff 渲染 (语法高亮)
- `add_message(msg)` / `update_part(part)` — 增量更新

**Test Plan (2 tests, Textual pilot):**
1. 添加 UserMessage → 渲染包含用户文本
2. 添加 AssistantMessage with ToolPart(completed) → 渲染包含 tool name 和展开按钮

---

## P4-S04: tui/dialogs.py — Permission + Session Dialogs `[ ]`

**Files:** `src/metiscode/tui/dialogs.py`, `tests/tui/test_dialogs.py`

**Dependencies:** P4-S01, P1-S09

**TS Reference:** Console app permission dialog (概念参考)

**Work:**
- `PermissionDialog(ModalScreen)`:
  - 显示: tool name, permission pattern, description
  - 按钮: "Allow Once" (y), "Allow Always" (a), "Reject" (n)
  - 快捷键: y/a/n
  - 触发 PermissionService.reply()
- `SessionPickerDialog(ModalScreen)`:
  - 列出所有 sessions (title, time, message count)
  - 选择 → 切换到该 session
  - 搜索/过滤
- `ModelSwitcherDialog(ModalScreen)`:
  - 列出所有 providers + models
  - 选择 → 切换当前 model
- 集成: 订阅 bus 的 `permission.ask` event → 自动弹出 PermissionDialog

**Test Plan (2 tests, Textual pilot):**
1. PermissionDialog 显示正确的 tool name 和 pattern
2. 点击 "Allow Once" → 调用 PermissionService.reply(id, "once")

---

## P4-S05: tui/themes.py + tui/keybindings.py — Themes & Keybindings `[ ]`

**Files:**
- `src/metiscode/tui/themes.py`
- `src/metiscode/tui/keybindings.py`

**Dependencies:** P4-S01, P1-S06

**TS Reference:** Console app theming (概念参考)

**Work:**
- `themes.py`:
  - `Theme` dataclass: name, colors (bg, fg, accent, error, warning, success, muted, border)
  - Built-in themes:
    - `dark` (默认): 深色背景, 亮色文字
    - `light`: 浅色背景, 深色文字
  - `load_theme(name: str) -> Theme`
  - 将 Theme 转换为 Textual CSS variables
- `keybindings.py`:
  - `Keybinding` dataclass: key, action, description
  - 默认 keybindings + 用户自定义 (from config)
  - `load_keybindings(config) -> list[Keybinding]`

**Test Plan (1 test):**
1. `load_theme("dark")` → 返回 Theme, bg 为深色值
