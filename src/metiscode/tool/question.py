"""Question tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define


class QuestionParams(BaseModel):
    """Parameters for question tool."""

    model_config = ConfigDict(extra="forbid")
    question: str
    options: list[str] | None = None


async def _execute_question(params: QuestionParams, ctx: ToolContext) -> ToolResult:
    patterns = params.options if params.options else [params.question]
    await ctx.ask("question", patterns)
    answer_text = ", ".join(params.options) if params.options else "Unanswered"
    return ToolResult(
        title="Question asked",
        output=f'User has answered your questions: "{params.question}"="{answer_text}".',
        metadata={"question": params.question, "options": params.options},
    )


def create_question_tool() -> ToolInfo[QuestionParams]:
    """Create question tool definition."""
    return define(
        "question",
        "Ask a question and collect user response options.",
        QuestionParams,
        _execute_question,
    )

