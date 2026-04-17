"""CLI entrypoint for metiscode."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from pydantic import BaseModel, ConfigDict

from metiscode.agent import AgentService
from metiscode.llm import LLMService
from metiscode.provider import HTTPStreamers, ProviderService
from metiscode.session import SessionDB, SessionProcessor, StreamInput, to_model_messages
from metiscode.tool import (
    ToolRegistry,
    create_bash_tool,
    create_edit_tool,
    create_glob_tool,
    create_grep_tool,
    create_plan_exit_tool,
    create_question_tool,
    create_read_tool,
    create_skill_tool,
    create_task_tool,
    create_todo_tool,
    create_webfetch_tool,
    create_websearch_tool,
    create_write_tool,
)
from metiscode.util.ids import ulid_str


class AssistantTurnStats(BaseModel):
    """Structured summary of assistant parts for one CLI turn."""

    model_config = ConfigDict(extra="forbid")
    has_text: bool = False
    has_tool: bool = False
    has_completed_tool: bool = False
    claims_file_action: bool = False


_FILE_ACTION_HINTS = (
    "创建",
    "修改",
    "编辑",
    "写入",
    "删除",
    "create",
    "created",
    "modify",
    "modified",
    "edit",
    "edited",
    "write",
    "wrote",
    "delete",
    "deleted",
    "file",
    ".py",
    ".ts",
    ".js",
    ".md",
    ".json",
    ".yaml",
    ".yml",
)

def _db() -> SessionDB:
    return SessionDB(project_id="global")


def _create_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(create_read_tool())
    registry.register(create_write_tool())
    registry.register(create_edit_tool())
    registry.register(create_glob_tool())
    registry.register(create_grep_tool())
    registry.register(create_bash_tool())
    registry.register(create_todo_tool())
    registry.register(create_question_tool())
    registry.register(create_plan_exit_tool())
    registry.register(create_skill_tool())
    registry.register(create_task_tool())
    registry.register(create_websearch_tool())
    registry.register(create_webfetch_tool())
    return registry


def _create_llm_service(provider_service: ProviderService) -> LLMService:
    streamers = HTTPStreamers(provider_service)
    return LLMService(
        provider_service=provider_service,
        anthropic_streamer=streamers.anthropic_streamer,
        openai_streamer=streamers.openai_streamer,
        deepseek_streamer=streamers.deepseek_streamer,
    )


def _tool_allowed_for_agent(tool_info: object, agent: str) -> bool:
    allowed_agents = getattr(tool_info, "allowed_agents", None)
    if not isinstance(allowed_agents, (set, list, tuple)):
        return True
    return agent in allowed_agents or "*" in allowed_agents


async def _tool_schemas(
    registry: ToolRegistry,
    *,
    agent: str,
    provider: str,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for tool_id in registry.ids():
        info = registry.get(tool_id)
        if info is None or not _tool_allowed_for_agent(info, agent):
            continue
        instance = await info.init(agent)
        schema = instance.parameters.model_json_schema()
        if provider == "anthropic":
            result.append(
                {
                    "name": tool_id,
                    "description": instance.description,
                    "input_schema": schema,
                }
            )
        else:
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_id,
                        "description": instance.description,
                        "parameters": schema,
                    },
                }
            )
    return result


async def _conversation_messages(db: SessionDB, session_id: str) -> list[dict[str, object]]:
    rows = await db.get_messages(session_id)
    result: list[dict[str, object]] = []
    for row in rows:
        message_id = row.get("id")
        role = row.get("role")
        if not isinstance(message_id, str) or not isinstance(role, str):
            continue
        data = row.get("data")
        parts: list[dict[str, object]] = []
        if isinstance(data, dict):
            raw_parts = data.get("parts")
            if isinstance(raw_parts, list):
                parts.extend(part for part in raw_parts if isinstance(part, dict))
        db_parts = await db.get_message_parts(message_id)
        for item in db_parts:
            payload = item.get("data")
            if isinstance(payload, dict):
                parts.append(payload)
        result.append({"role": role, "parts": parts})
    return result


def _contains_file_action_hint(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _FILE_ACTION_HINTS)


def _echo_assistant_parts(parts: list[dict[str, object]]) -> AssistantTurnStats:
    stats = AssistantTurnStats()
    for part in parts:
        data = part.get("data")
        if not isinstance(data, dict):
            continue
        part_type = data.get("type")
        if part_type == "text":
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                stats.has_text = True
                if _contains_file_action_hint(content):
                    stats.claims_file_action = True
                click.echo(content)
        elif part_type == "tool":
            stats.has_tool = True
            tool_id = data.get("tool_id")
            state = data.get("state")
            output = data.get("output")
            if state == "completed":
                stats.has_completed_tool = True
            if isinstance(tool_id, str) and isinstance(state, str):
                click.echo(f"[tool:{state}] {tool_id}")
            if isinstance(output, str) and output.strip():
                click.echo(output)
        elif part_type == "reasoning":
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                click.echo(f"[reasoning] {content}")
    return stats


def _should_fail_claimed_file_action(
    *,
    stats: AssistantTurnStats,
    has_any_completed_tool: bool,
) -> bool:
    return stats.claims_file_action and not stats.has_completed_tool and not has_any_completed_tool


def _should_warn_requested_file_action(
    *,
    prompt_requests_file_action: bool,
    stats: AssistantTurnStats,
    has_any_completed_tool: bool,
) -> bool:
    return (
        prompt_requests_file_action
        and not stats.has_completed_tool
        and not has_any_completed_tool
    )


async def _ensure_session(
    db: SessionDB,
    *,
    maybe_session_id: str | None,
    prompt: str,
) -> str:
    await db.init()
    if maybe_session_id:
        existing = await db.get_session(maybe_session_id)
        if existing is None:
            raise click.ClickException(f"session not found: {maybe_session_id}")
        return maybe_session_id

    session_id = ulid_str()
    title = prompt.strip()[:40] or "New session"
    await db.create_session(
        session_id=session_id,
        slug=f"session-{session_id[:6].lower()}",
        directory=str(Path(".").resolve()),
        title=title,
    )
    return session_id


async def _append_user_message(db: SessionDB, *, session_id: str, prompt: str) -> None:
    await db.create_message(
        message_id=ulid_str(),
        session_id=session_id,
        role="user",
        data={"parts": [{"type": "text", "content": prompt}]},
    )


async def _run_prompt(model: str, agent: str, session_id: str | None, prompt: str) -> str:
    provider_service = ProviderService()
    model_ref = provider_service.parse_model(model)
    agent_info = AgentService().get(agent)
    llm = _create_llm_service(provider_service)
    registry = _create_registry()
    db = _db()
    resolved_session_id = await _ensure_session(db, maybe_session_id=session_id, prompt=prompt)
    await _append_user_message(db, session_id=resolved_session_id, prompt=prompt)
    prompt_requests_file_action = _contains_file_action_hint(prompt)

    click.echo(f"session_id={resolved_session_id}")
    max_steps = max(1, agent_info.max_steps)
    has_any_completed_tool = False

    for _ in range(max_steps):
        assistant_message_id = ulid_str()
        await db.create_message(
            message_id=assistant_message_id,
            session_id=resolved_session_id,
            role="assistant",
            data={"parts": [], "model": model},
        )
        messages = await _conversation_messages(db, resolved_session_id)
        tools = await _tool_schemas(registry, agent=agent, provider=model_ref.provider_id)
        processor = SessionProcessor.create(
            session_id=resolved_session_id,
            assistant_message_id=assistant_message_id,
            model=model,
            agent=agent,
            abort=asyncio.Event(),
            llm=llm,
            registry=registry,
            db=db,
            bus=None,
        )
        result = await processor.process(
            StreamInput(
                model=model,
                messages=to_model_messages(messages, provider=model_ref.provider_id),
                tools=tools,
                system=f"Agent: {agent}",
            )
        )
        stats = _echo_assistant_parts(await db.get_message_parts(assistant_message_id))
        has_any_completed_tool = has_any_completed_tool or stats.has_completed_tool
        if not stats.has_text and not stats.has_tool:
            raise click.ClickException(
                "assistant returned empty output (no text/tool). "
                "Check provider API key or provider response parsing."
            )
        if _should_fail_claimed_file_action(
            stats=stats,
            has_any_completed_tool=has_any_completed_tool,
        ):
            raise click.ClickException(
                "assistant claimed file operations, but no completed tool call was recorded."
            )
        if _should_warn_requested_file_action(
            prompt_requests_file_action=prompt_requests_file_action,
            stats=stats,
            has_any_completed_tool=has_any_completed_tool,
        ):
            click.echo("[warn] requested file action, but no completed tool call was recorded.")
        if result == "stop":
            return resolved_session_id
        if result == "compact":
            raise click.ClickException("context overflow: compaction not wired in CLI yet")

    raise click.ClickException(f"max steps exceeded ({max_steps})")


@click.group()
def cli() -> None:
    """MetisCode command line interface."""


@cli.command()
@click.option("--model", default="anthropic:claude-sonnet-4-20250514", show_default=True)
@click.option("--agent", default="build", show_default=True)
@click.option("--session-id", default=None)
@click.argument("prompt")
def run(model: str, agent: str, session_id: str | None, prompt: str) -> None:
    """Run a single prompt."""
    click.echo(f"model={model}")
    click.echo(f"agent={agent}")
    if session_id:
        click.echo(f"session_id={session_id}")
    asyncio.run(_run_prompt(model=model, agent=agent, session_id=session_id, prompt=prompt))


@cli.command()
@click.option("--port", default=4096, show_default=True, type=int)
@click.option("--host", default="127.0.0.1", show_default=True)
def serve(port: int, host: str) -> None:
    """Start HTTP server placeholder."""
    click.echo(f"Serving on http://{host}:{port}")


@cli.group()
def session() -> None:
    """Session management commands."""


@session.command("list")
def session_list() -> None:
    """List sessions for current project."""
    db = _db()

    async def _run() -> list[dict[str, object]]:
        await db.init()
        return await db.list_sessions()

    sessions = asyncio.run(_run())
    if not sessions:
        click.echo("[]")
        return
    for item in sessions:
        click.echo(f"{item['id']}\t{item['title']}")


@session.command("show")
@click.argument("session_id")
def session_show(session_id: str) -> None:
    """Show one session."""
    db = _db()

    async def _run() -> dict[str, object] | None:
        await db.init()
        return await db.get_session(session_id)

    result = asyncio.run(_run())
    click.echo(str(result))


@session.command("delete")
@click.argument("session_id")
def session_delete(session_id: str) -> None:
    """Delete one session."""
    db = _db()

    async def _run() -> None:
        await db.init()
        await db.delete_session(session_id)

    asyncio.run(_run())
    click.echo(f"deleted {session_id}")


@cli.command()
def tui() -> None:
    """Launch TUI placeholder."""
    click.echo("TUI is not implemented yet.")
