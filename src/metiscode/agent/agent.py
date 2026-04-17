"""Agent registry and built-in agent definitions."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from metiscode.permission import Rule, Ruleset, from_config

AgentMode = Literal["primary", "subagent", "all"]


class AgentInfo(BaseModel):
    """Agent configuration model."""

    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    mode: AgentMode
    hidden: bool = False
    permission: Ruleset = Field(default_factory=list)
    model: str | None = None
    prompt: str | None = None
    tools: list[str] | None = None
    max_steps: int = 50
    temperature: float | None = None
    top_p: float | None = None


def _base_permission() -> Ruleset:
    return from_config(
        {
            "*": "allow",
            "external_directory": {"*": "ask"},
            "question": "deny",
            "plan_enter": "deny",
            "plan_exit": "deny",
        }
    )


def _deny_all() -> Ruleset:
    return [Rule(permission="*", pattern="*", action="deny")]


def _builtin_agents() -> dict[str, AgentInfo]:
    base = _base_permission()
    return {
        "build": AgentInfo(
            name="build",
            description="Default build agent with editing capabilities.",
            mode="primary",
            permission=[
                *base,
                Rule(permission="question", pattern="*", action="allow"),
                Rule(permission="plan_enter", pattern="*", action="allow"),
            ],
        ),
        "plan": AgentInfo(
            name="plan",
            description="Planning agent that blocks normal edits.",
            mode="primary",
            permission=[
                *base,
                Rule(permission="question", pattern="*", action="allow"),
                Rule(permission="plan_exit", pattern="*", action="allow"),
                Rule(permission="edit", pattern="*", action="deny"),
                Rule(permission="edit", pattern="plans/*", action="allow"),
            ],
        ),
        "general": AgentInfo(
            name="general",
            description="General-purpose subagent.",
            mode="subagent",
            permission=[*base, Rule(permission="todowrite", pattern="*", action="deny")],
        ),
        "explore": AgentInfo(
            name="explore",
            description="Read-only exploration subagent.",
            mode="subagent",
            permission=[
                Rule(permission="*", pattern="*", action="deny"),
                Rule(permission="read", pattern="*", action="allow"),
                Rule(permission="glob", pattern="*", action="allow"),
                Rule(permission="grep", pattern="*", action="allow"),
                Rule(permission="webfetch", pattern="*", action="allow"),
                Rule(permission="websearch", pattern="*", action="allow"),
            ],
        ),
        "compaction": AgentInfo(
            name="compaction",
            mode="primary",
            hidden=True,
            permission=_deny_all(),
        ),
        "title": AgentInfo(
            name="title",
            mode="primary",
            hidden=True,
            permission=_deny_all(),
            temperature=0.5,
        ),
        "summary": AgentInfo(
            name="summary",
            mode="primary",
            hidden=True,
            permission=_deny_all(),
        ),
    }


class AgentService:
    """In-memory agent service with built-ins and optional overrides."""

    def __init__(self, *, overrides: dict[str, dict[str, object]] | None = None) -> None:
        self._agents = _builtin_agents()
        if overrides:
            self._apply_overrides(overrides)

    def _apply_overrides(self, overrides: dict[str, dict[str, object]]) -> None:
        for name, data in overrides.items():
            if name not in self._agents:
                self._agents[name] = AgentInfo(name=name, mode="all", permission=_base_permission())
            existing = self._agents[name]
            payload = existing.model_dump()
            payload.update(data)
            self._agents[name] = AgentInfo.model_validate(payload)

    def get(self, name: str) -> AgentInfo:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name}")
        return deepcopy(self._agents[name])

    def list(self) -> list[AgentInfo]:
        visible = [agent for agent in self._agents.values() if not agent.hidden]
        visible.sort(key=lambda item: item.name)
        return [deepcopy(agent) for agent in visible]

    def default_agent(self) -> AgentInfo:
        return self.get("build")

