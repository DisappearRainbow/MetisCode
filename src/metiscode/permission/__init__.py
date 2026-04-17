"""Permission rule conversion and evaluation."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from metiscode.util.wildcard import match

PermissionAction = Literal["allow", "deny", "ask"]


class Rule(BaseModel):
    """Permission rule."""

    model_config = ConfigDict(extra="forbid")
    permission: str
    pattern: str
    action: PermissionAction


Ruleset = list[Rule]
ConfigPermission = Mapping[str, PermissionAction | Mapping[str, PermissionAction]]

_EDIT_TOOLS = {"edit", "write", "apply_patch", "multiedit"}


def evaluate(permission: str, pattern: str, *rulesets: Ruleset) -> Rule:
    """Evaluate permission rule: last matching rule wins, default ask."""
    rules = [rule for ruleset in rulesets for rule in ruleset]
    for rule in reversed(rules):
        if match(permission, rule.permission) and match(pattern, rule.pattern):
            return rule
    return Rule(permission=permission, pattern="*", action="ask")


def _expand(pattern: str) -> str:
    home = os.path.expanduser("~")
    if pattern.startswith("~/"):
        return home + pattern[1:]
    if pattern == "~":
        return home
    if pattern.startswith("$HOME/"):
        return home + pattern[5:]
    if pattern.startswith("$HOME"):
        return home + pattern[5:]
    return pattern


def from_config(permission_config: ConfigPermission) -> Ruleset:
    """Convert config-style permission mapping into ordered ruleset."""
    rules: Ruleset = []
    for permission, value in permission_config.items():
        if isinstance(value, str):
            rules.append(Rule(permission=permission, pattern="*", action=value))
            continue
        for pattern, action in value.items():
            rules.append(Rule(permission=permission, pattern=_expand(pattern), action=action))
    return rules


def merge(*rulesets: Ruleset) -> Ruleset:
    """Merge rulesets by concatenation."""
    return [rule for ruleset in rulesets for rule in ruleset]


def disabled(tools: Iterable[str], ruleset: Ruleset) -> set[str]:
    """Return tools disabled by wildcard deny rule with pattern '*'."""
    result: set[str] = set()
    for tool in tools:
        permission = "edit" if tool in _EDIT_TOOLS else tool
        last_match: Rule | None = None
        for rule in ruleset:
            if match(permission, rule.permission):
                last_match = rule
        if last_match and last_match.pattern == "*" and last_match.action == "deny":
            result.add(tool)
    return result
