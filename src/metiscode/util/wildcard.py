"""Wildcard matching utilities."""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping, Sequence


def _escape_pattern(pattern: str) -> str:
    special_chars = ".+^${}()|[]\\"
    escaped: list[str] = []
    for char in pattern:
        if char in special_chars:
            escaped.append("\\")
        escaped.append(char)
    return "".join(escaped)


def match(value: str, pattern: str) -> bool:
    """Match a value against wildcard pattern with OpenCode-compatible semantics."""
    normalized_value = value.replace("\\", "/") if value else value
    normalized_pattern = pattern.replace("\\", "/") if pattern else pattern

    escaped = _escape_pattern(normalized_pattern).replace("*", ".*").replace("?", ".")
    if escaped.endswith(" .*"):
        escaped = escaped[:-3] + "( .*)?"

    flags = re.DOTALL | (re.IGNORECASE if sys.platform == "win32" else 0)
    return re.fullmatch(escaped, normalized_value, flags=flags) is not None


def all_matches(value: str, patterns: Mapping[str, object]) -> object | None:
    """Return last match when patterns are sorted by (length, key)."""
    sorted_items = sorted(patterns.items(), key=lambda item: (len(item[0]), item[0]))
    result: object | None = None
    for pattern, matched_value in sorted_items:
        if match(value, pattern):
            result = matched_value
    return result


def _match_sequence(items: Sequence[str], patterns: Sequence[str]) -> bool:
    if not patterns:
        return True
    pattern = patterns[0]
    rest = patterns[1:]
    if pattern == "*":
        return _match_sequence(items, rest)
    for index, item in enumerate(items):
        if match(item, pattern) and _match_sequence(items[index + 1 :], rest):
            return True
    return False


def all_structured(
    input_value: dict[str, str | list[str]],
    patterns: Mapping[str, object],
) -> object | None:
    """Match command head/tail patterns and return last match by sorted order."""
    head_raw = input_value.get("head")
    tail_raw = input_value.get("tail")
    if not isinstance(head_raw, str) or not isinstance(tail_raw, list):
        return None
    if not all(isinstance(item, str) for item in tail_raw):
        return None

    sorted_items = sorted(patterns.items(), key=lambda item: (len(item[0]), item[0]))
    result: object | None = None
    for pattern, matched_value in sorted_items:
        parts = re.split(r"\s+", pattern.strip()) if pattern.strip() else [pattern]
        if not parts or not match(head_raw, parts[0]):
            continue
        if len(parts) == 1 or _match_sequence(tail_raw, parts[1:]):
            result = matched_value
    return result
