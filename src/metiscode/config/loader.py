"""Config loader with JSONC support and deterministic precedence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError

from metiscode.config.schema import ConfigInfo
from metiscode.util.errors import MetiscodeError

log = structlog.get_logger(__name__)


class ConfigJsonError(MetiscodeError):
    """Raised when JSONC cannot be parsed."""

    def __init__(self, *, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


class ConfigInvalidError(MetiscodeError):
    """Raised when parsed JSON does not match schema."""

    def __init__(self, *, path: str, issues: str) -> None:
        super().__init__(f"{path}: {issues}")
        self.path = path
        self.issues = issues


def _strip_jsonc_comments(text: str) -> str:
    output: list[str] = []
    i = 0
    in_string = False
    escaped = False
    length = len(text)

    while i < length:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < length else ""

        if in_string:
            output.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            output.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < length and text[i] not in ("\n", "\r"):
                i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < length and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        output.append(ch)
        i += 1

    return "".join(output)


def _remove_trailing_commas(text: str) -> str:
    output: list[str] = []
    i = 0
    in_string = False
    escaped = False
    length = len(text)

    while i < length:
        ch = text[i]

        if in_string:
            output.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            output.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < length and text[j] in (" ", "\t", "\n", "\r"):
                j += 1
            if j < length and text[j] in ("]", "}"):
                i += 1
                continue

        output.append(ch)
        i += 1

    return "".join(output)


def _parse_jsonc(text: str, path: str) -> dict[str, Any]:
    stripped = _strip_jsonc_comments(text)
    no_trailing = _remove_trailing_commas(stripped)
    try:
        parsed = json.loads(no_trailing)
    except json.JSONDecodeError as exc:
        raise ConfigJsonError(path=path, message=str(exc)) from exc

    if not isinstance(parsed, dict):
        raise ConfigJsonError(path=path, message="top-level config must be an object")
    return parsed


def parse_config_text(text: str, source: str) -> ConfigInfo:
    """Parse JSONC text into validated config model."""
    parsed = _parse_jsonc(text, source)
    try:
        return ConfigInfo.model_validate(parsed)
    except ValidationError as exc:
        raise ConfigInvalidError(path=source, issues=exc.json(indent=2)) from exc


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    merged = dict(target)
    for key, source_value in source.items():
        target_value = merged.get(key)
        if isinstance(target_value, dict) and isinstance(source_value, dict):
            merged[key] = _deep_merge(target_value, source_value)
        else:
            merged[key] = source_value
    return merged


def merge_config_concat_arrays(target: ConfigInfo, source: ConfigInfo) -> ConfigInfo:
    """Deep merge config where plugin/instructions arrays are concatenated and deduplicated."""
    target_dict = target.model_dump(by_alias=True, exclude_none=True)
    source_dict = source.model_dump(by_alias=True, exclude_none=True)

    merged = _deep_merge(target_dict, source_dict)
    for key in ("plugin", "instructions"):
        target_array = target_dict.get(key)
        source_array = source_dict.get(key)
        if isinstance(target_array, list) and isinstance(source_array, list):
            merged[key] = list(dict.fromkeys([*target_array, *source_array]))

    return ConfigInfo.model_validate(merged)


def _read_optional_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def load_config_hierarchy(
    *,
    global_file: Path | None = None,
    project_files: list[Path] | None = None,
    env_content: str | None = None,
) -> ConfigInfo:
    """Load config with precedence: global < project files < env content."""
    result = ConfigInfo.model_validate({})

    if global_file is not None:
        global_text = _read_optional_file(global_file)
        if global_text is not None:
            parsed_global = parse_config_text(global_text, str(global_file))
            result = merge_config_concat_arrays(result, parsed_global)
            log.debug("loaded global config", path=str(global_file))

    for file in project_files or []:
        project_text = _read_optional_file(file)
        if project_text is None:
            continue
        result = merge_config_concat_arrays(result, parse_config_text(project_text, str(file)))
        log.debug("loaded project config", path=str(file))

    if env_content:
        parsed_env = parse_config_text(env_content, "OPENCODE_CONFIG_CONTENT")
        result = merge_config_concat_arrays(result, parsed_env)
        log.debug("loaded env config content")

    return result
