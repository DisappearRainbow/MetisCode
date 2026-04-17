"""Tool definition factory and runtime wrappers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from metiscode.tool.truncate import truncate_output

ParametersModelT = TypeVar("ParametersModelT", bound=BaseModel)


@dataclass(slots=True)
class ToolContext:
    """Runtime context passed to tool execution."""

    session_id: str
    message_id: str
    agent: str
    abort: asyncio.Event
    metadata: Callable[[dict[str, object]], None]
    ask: Callable[[str, list[str]], Awaitable[None]]
    call_id: str | None = None
    extra: dict[str, object] | None = None
    messages: list[object] = field(default_factory=list)


@dataclass(slots=True)
class ToolResult:
    """Tool execution output."""

    title: str
    output: str
    metadata: dict[str, object] = field(default_factory=dict)
    attachments: list[dict[str, object]] | None = None


class ToolInstance(Generic[ParametersModelT]):  # noqa: UP046
    """Initialized tool executable with schema and description."""

    def __init__(
        self,
        *,
        description: str,
        parameters: type[ParametersModelT],
        execute: Callable[[dict[str, object], ToolContext], Awaitable[ToolResult]],
        format_validation_error: Callable[[ValidationError], str] | None = None,
    ) -> None:
        self.description = description
        self.parameters = parameters
        self.execute = execute
        self.format_validation_error = format_validation_error


class ToolInfo(Generic[ParametersModelT]):  # noqa: UP046
    """Tool descriptor that can be initialized for an agent context."""

    def __init__(
        self,
        *,
        tool_id: str,
        init: Callable[[str | None], Awaitable[ToolInstance[ParametersModelT]]],
    ) -> None:
        self.id = tool_id
        self.init = init


def define(  # noqa: UP047
    tool_id: str,
    description: str,
    parameters: type[ParametersModelT],
    execute_fn: Callable[[ParametersModelT, ToolContext], Awaitable[ToolResult]],
    *,
    format_validation_error: Callable[[ValidationError], str] | None = None,
    max_output_chars: int = 80_000,
) -> ToolInfo[ParametersModelT]:
    """Define a tool with validation + truncation wrapper."""

    async def init(_agent: str | None = None) -> ToolInstance[ParametersModelT]:
        async def execute(args: dict[str, object], ctx: ToolContext) -> ToolResult:
            try:
                parsed = parameters.model_validate(args)
            except ValidationError as error:
                if format_validation_error is not None:
                    raise ValueError(format_validation_error(error)) from error
                raise

            result = await execute_fn(parsed, ctx)
            if "truncated" in result.metadata:
                return result

            truncated_result = truncate_output(result.output, max_chars=max_output_chars)
            metadata = dict(result.metadata)
            metadata["truncated"] = truncated_result.truncated
            if truncated_result.overflow_path:
                metadata["outputPath"] = truncated_result.overflow_path
            return ToolResult(
                title=result.title,
                output=truncated_result.output,
                metadata=metadata,
                attachments=result.attachments,
            )

        return ToolInstance(
            description=description,
            parameters=parameters,
            execute=execute,
            format_validation_error=format_validation_error,
        )

    return ToolInfo(tool_id=tool_id, init=init)
