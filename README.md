# metiscode

`metiscode` 是一个基于 Python 3.12+ 的 AI Coding Agent，目标是移植并简化 OpenCode 的核心能力：  
多模型流式推理、工具调用、权限控制、SQLite 会话持久化、HTTP 服务与 Textual TUI。

## 主要能力

- 多模型支持：Anthropic / OpenAI / DeepSeek
- 工具系统：`read` / `write` / `edit` / `bash` / `glob` / `grep` / `task` / `todo` / `websearch` / `webfetch` 等
- 权限控制：支持 `allow / ask / deny` 规则
- 会话持久化：SQLite 保存消息、parts、任务上下文
- 交互方式：CLI、FastAPI（SSE/WS）、Textual TUI

## 环境要求

- Python `>=3.12`
- Windows 环境推荐使用（仓库当前按 Windows 命令与路径约定维护）

本项目默认开发环境（仓库内约定）：

```powershell
$PY = "C:/Users/18742/.conda/envs/metiscode312/python.exe"
```

## 安装

```powershell
& $PY -m pip install -e ".[dev]"
```

## 鉴权配置

在环境变量或 `.env` 中设置（至少一个）：

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`

示例 `.env`：

```dotenv
DEEPSEEK_API_KEY=sk-xxxx
```

## 快速开始

### 1) CLI 对话

```powershell
& $PY -m metiscode run --model deepseek:deepseek-chat "say hello in one word"
```

### 2) 启动 HTTP 服务

```powershell
& $PY -m metiscode serve --host 127.0.0.1 --port 4096
```

### 3) 启动 TUI

```powershell
& $PY -m metiscode tui
```

### 4) 会话管理

```powershell
& $PY -m metiscode session list
& $PY -m metiscode session show <session_id>
& $PY -m metiscode session delete <session_id>
```

## 常用运行时开关

- `METISCODE_DB_PATH`：覆盖 SQLite 路径
- `METISCODE_PERMISSION_RULES`：注入权限规则（JSON）
- `METISCODE_PERMISSION_ASK=deny|allow`：控制 `ask` 动作策略
- `METISCODE_E2E=1`：启用真实 provider 的 e2e 测试

示例：

```powershell
$env:METISCODE_PERMISSION_RULES='{"edit":{"*":"deny"}}'
& $PY -m metiscode run --model deepseek:deepseek-chat "create a.py that prints hi"
```

## 测试与质量检查

```powershell
& $PY -m ruff check src tests
& $PY -m mypy src/metiscode
& $PY -m pytest -q -p no:cacheprovider
& $PY -m pytest -q -m e2e tests/integration -p no:cacheprovider
```

## 目录结构（核心）

```text
src/metiscode/
  cli/         # 命令入口
  session/     # DB、消息、processor
  tool/        # 工具定义与实现
  provider/    # 模型提供方抽象
  server/      # FastAPI + SSE + WS
  tui/         # Textual 客户端
  permission/  # 权限规则匹配
```

## 参考与说明

- 参考实现：`./opencode/`（只读，不修改）
- 详细移植计划：`PLAN.md`
- 代理协作约束：`AGENTS.md`

