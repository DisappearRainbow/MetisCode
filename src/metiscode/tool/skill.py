"""Skill tool stub."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from metiscode.skill import SkillLoader
from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define


class SkillParams(BaseModel):
    """Parameters for skill tool."""

    model_config = ConfigDict(extra="forbid")
    skill_name: str
    args: str | None = None


async def _execute_skill(params: SkillParams, ctx: ToolContext) -> ToolResult:
    await ctx.ask("skill", [params.skill_name])

    skills: dict[str, str] = {}
    if isinstance(ctx.extra, dict):
        loaded_skills = ctx.extra.get("skills")
        if isinstance(loaded_skills, dict):
            skills = {str(key): str(value) for key, value in loaded_skills.items()}
    if not skills:
        loader = SkillLoader()
        discovered = loader.load_all()
        skills = {name: info.system_prompt for name, info in discovered.items()}

    if params.skill_name not in skills:
        raise ValueError(f'skill not found: "{params.skill_name}"')

    content = skills[params.skill_name]
    return ToolResult(
        title=f"Loaded skill: {params.skill_name}",
        output=content,
        metadata={"skill_name": params.skill_name, "args": params.args},
    )


def create_skill_tool() -> ToolInfo[SkillParams]:
    """Create skill tool definition."""
    return define(
        "skill",
        "Load skill instructions by name (stub in v1).",
        SkillParams,
        _execute_skill,
    )
