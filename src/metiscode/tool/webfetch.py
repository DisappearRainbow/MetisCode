"""Web fetch tool."""

from __future__ import annotations

import re
import time
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define

_CACHE_LIMIT = 15
_CACHE: dict[str, tuple[float, str, str]] = {}


class WebFetchParams(BaseModel):
    """Parameters for webfetch tool."""

    model_config = ConfigDict(extra="forbid")
    url: str
    prompt: str | None = None


def _fetch_url(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "metiscode/0.1"})  # noqa: S310
    with urlopen(request, timeout=15) as response:  # noqa: S310
        final_url = response.geturl()
        body = response.read().decode("utf-8", errors="ignore")
    return final_url, body


def _to_text(html: str) -> str:
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _cache_set(url: str, final_url: str, text: str) -> None:
    _CACHE[url] = (time.time(), final_url, text)
    if len(_CACHE) <= _CACHE_LIMIT:
        return
    oldest_key = min(_CACHE.items(), key=lambda item: item[1][0])[0]
    _CACHE.pop(oldest_key, None)


async def _execute_webfetch(params: WebFetchParams, ctx: ToolContext) -> ToolResult:
    await ctx.ask("webfetch", [params.url])
    if params.url in _CACHE:
        _timestamp, final_url, text = _CACHE[params.url]
        return ToolResult(
            title=final_url,
            output=text,
            metadata={"url": params.url, "final_url": final_url, "cached": True},
        )

    final_url, html = _fetch_url(params.url)
    text = _to_text(html)
    _cache_set(params.url, final_url, text)
    return ToolResult(
        title=final_url,
        output=text,
        metadata={"url": params.url, "final_url": final_url, "cached": False},
    )


def create_webfetch_tool() -> ToolInfo[WebFetchParams]:
    """Create webfetch tool definition."""
    return define(
        "webfetch",
        "Fetch a web page and convert it into plain text.",
        WebFetchParams,
        _execute_webfetch,
    )

