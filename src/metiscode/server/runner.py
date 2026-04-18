"""Background turn runner for server message endpoint."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable, Mapping
from typing import cast

from metiscode.agent import AgentService
from metiscode.bus import (
    MESSAGE_COMPLETED,
    PART_CREATED,
    EventBus,
    MessageCompleted,
    PartCreated,
)
from metiscode.llm import LLMService
from metiscode.permission import ConfigPermission, Rule, evaluate, from_config, merge
from metiscode.provider import HTTPStreamers, ProviderService
from metiscode.session import SessionDB, SessionProcessor, StreamInput, prune, to_model_messages
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
from metiscode.util.errors import PermissionDeniedError
from metiscode.util.ids import ulid_str


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


def _load_runtime_permission_rules() -> list[Rule]:
    raw = os.getenv("METISCODE_PERMISSION_RULES", "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, Mapping):
        return []
    permission_config = cast(ConfigPermission, parsed)
    return from_config(permission_config)


def _permission_ask_mode() -> str:
    mode = os.getenv("METISCODE_PERMISSION_ASK", "allow").strip().lower()
    return "deny" if mode == "deny" else "allow"


def _build_permission_ask(
    rules: list[Rule],
) -> Callable[[str, list[str]], Awaitable[None]]:
    ask_mode = _permission_ask_mode()

    async def _ask(permission: str, patterns: list[str]) -> None:
        candidates = patterns or ["*"]
        for pattern in candidates:
            decision = evaluate(permission, pattern, rules)
            if decision.action == "deny":
                raise PermissionDeniedError(
                    f"Permission denied: {permission}:{pattern} (matched deny rule)"
                )
            if decision.action == "ask" and ask_mode == "deny":
                raise PermissionDeniedError(
                    f"Permission denied: {permission}:{pattern} (ask blocked by runtime policy)"
                )

    return _ask


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


async def run_session_turn(
    *,
    db: SessionDB,
    bus: EventBus,
    session_id: str,
    model: str,
    agent: str,
) -> None:
    try:
        provider_service = ProviderService()
        model_ref = provider_service.parse_model(model)
        provider_service.require_credentials(model_ref)
        model_info = provider_service.get_model(model_ref.provider_id, model_ref.model_id)
        agent_info = AgentService().get(agent)
        runtime_permission_rules = _load_runtime_permission_rules()
        permission_rules = merge(agent_info.permission, runtime_permission_rules)
        permission_ask = _build_permission_ask(permission_rules)
        llm = _create_llm_service(provider_service)
        registry = _create_registry()

        compacted_last_step = False
        max_steps = max(1, agent_info.max_steps)
        for _ in range(max_steps):
            assistant_message_id = ulid_str()
            await db.create_message(
                message_id=assistant_message_id,
                session_id=session_id,
                role="assistant",
                data={"parts": [], "model": model},
            )
            messages = await _conversation_messages(db, session_id)
            tools = await _tool_schemas(registry, agent=agent, provider=model_ref.provider_id)
            processor = SessionProcessor.create(
                session_id=session_id,
                assistant_message_id=assistant_message_id,
                model=model,
                agent=agent,
                abort=asyncio.Event(),
                llm=llm,
                registry=registry,
                db=db,
                bus=bus,
            )
            processor.permission_ask = permission_ask
            result = await processor.process(
                StreamInput(
                    model=model,
                    messages=to_model_messages(messages, provider=model_ref.provider_id),
                    tools=tools,
                    system=f"Agent: {agent}",
                )
            )
            if result == "stop":
                return
            if result == "compact":
                if compacted_last_step:
                    raise RuntimeError("context overflow persists after compaction")
                await prune(session_id, model_info, db)
                compacted_last_step = True
                continue
            compacted_last_step = False
    except Exception as error:  # noqa: BLE001
        assistant_message_id = ulid_str()
        part_id = ulid_str()
        error_part = {"type": "text", "content": f"ServerError: {error}"}
        await db.create_message(
            message_id=assistant_message_id,
            session_id=session_id,
            role="assistant",
            data={"parts": [], "model": model},
        )
        await db.create_part(
            part_id=part_id,
            message_id=assistant_message_id,
            session_id=session_id,
            part_type="text",
            data=error_part,
        )
        await bus.publish(
            PART_CREATED,
            PartCreated(
                session_id=session_id,
                message_id=assistant_message_id,
                part_id=part_id,
                data=error_part,
            ),
        )
        await bus.publish(
            MESSAGE_COMPLETED,
            MessageCompleted(
                session_id=session_id,
                message_id=assistant_message_id,
                role="assistant",
            ),
        )
