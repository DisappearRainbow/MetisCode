"""Web search tool."""

from __future__ import annotations

import json
from urllib.parse import quote_plus
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field

from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define


class WebSearchParams(BaseModel):
    """Parameters for websearch tool."""

    model_config = ConfigDict(extra="forbid")
    query: str
    num_results: int = Field(default=5, ge=1, le=20)


def _fetch_json(query: str) -> dict[str, object]:
    encoded = quote_plus(query)
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
    with urlopen(url, timeout=10) as response:  # noqa: S310
        payload = response.read().decode("utf-8", errors="ignore")
    data = json.loads(payload)
    if not isinstance(data, dict):
        return {}
    return data


def _extract_results(data: dict[str, object], limit: int) -> list[tuple[str, str, str]]:
    related_topics = data.get("RelatedTopics")
    if not isinstance(related_topics, list):
        return []

    results: list[tuple[str, str, str]] = []
    for item in related_topics:
        if isinstance(item, dict) and "Topics" in item:
            nested = item.get("Topics")
            if isinstance(nested, list):
                for nested_item in nested:
                    if not isinstance(nested_item, dict):
                        continue
                    text = nested_item.get("Text")
                    first_url = nested_item.get("FirstURL")
                    if isinstance(text, str) and isinstance(first_url, str):
                        results.append((text, first_url, text))
        elif isinstance(item, dict):
            text = item.get("Text")
            first_url = item.get("FirstURL")
            if isinstance(text, str) and isinstance(first_url, str):
                results.append((text, first_url, text))
        if len(results) >= limit:
            break
    return results[:limit]


async def _execute_websearch(params: WebSearchParams, ctx: ToolContext) -> ToolResult:
    await ctx.ask("websearch", [params.query])
    data = _fetch_json(params.query)
    results = _extract_results(data, params.num_results)
    if not results:
        return ToolResult(
            title=params.query,
            output="No results found",
            metadata={"count": 0},
        )

    lines = []
    for index, (title, url, snippet) in enumerate(results, start=1):
        lines.append(f"{index}. {title}")
        lines.append(f"   URL: {url}")
        lines.append(f"   Snippet: {snippet}")
    return ToolResult(
        title=params.query,
        output="\n".join(lines),
        metadata={"count": len(results)},
    )


def create_websearch_tool() -> ToolInfo[WebSearchParams]:
    """Create websearch tool definition."""
    return define(
        "websearch",
        "Search the web and return title/url/snippet results.",
        WebSearchParams,
        _execute_websearch,
    )

