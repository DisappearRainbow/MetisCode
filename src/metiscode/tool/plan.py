"""Plan mode helper tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define


class PlanExitParams(BaseModel):
    """Parameters for plan exit tool."""

    model_config = ConfigDict(extra="forbid")


async def _execute_plan_exit(_params: PlanExitParams, _ctx: ToolContext) -> ToolResult:
    return ToolResult(
        title="Switching to build agent",
        output="Plan complete. Switch to build agent to continue implementation.",
        metadata={"plan_exit": True},
    )


def create_plan_exit_tool() -> ToolInfo[PlanExitParams]:
    """Create plan-exit tool definition."""
    return define(
        "plan_exit",
        "Exit planning mode and request transition to build mode.",
        PlanExitParams,
        _execute_plan_exit,
    )

