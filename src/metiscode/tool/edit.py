"""Edit tool and replacement strategies."""

from __future__ import annotations

import re
from collections.abc import Callable, Generator
from difflib import unified_diff
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from metiscode.project.service import contains_path
from metiscode.tool.tool import ToolContext, ToolInfo, ToolResult, define

Replacer = Callable[[str, str], Generator[str, None, None]]
SINGLE_CANDIDATE_SIMILARITY_THRESHOLD = 0.0
MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD = 0.3


def normalize_line_endings(text: str) -> str:
    """Normalize CRLF to LF for robust matching."""
    return text.replace("\r\n", "\n")


def detect_line_ending(text: str) -> str:
    """Detect newline style from text."""
    return "\r\n" if "\r\n" in text else "\n"


def convert_to_line_ending(text: str, ending: str) -> str:
    """Convert LF text to requested newline style."""
    if ending == "\n":
        return text
    return text.replace("\n", "\r\n")


def SimpleReplacer(_content: str, find: str) -> Generator[str, None, None]:  # noqa: N802
    yield find


def levenshtein_distance(a: str, b: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if a == b:
        return 0
    if a == "" or b == "":
        return max(len(a), len(b))

    matrix = [[0 for _ in range(len(b) + 1)] for _ in range(len(a) + 1)]
    for index in range(len(a) + 1):
        matrix[index][0] = index
    for index in range(len(b) + 1):
        matrix[0][index] = index

    for a_index in range(1, len(a) + 1):
        for b_index in range(1, len(b) + 1):
            cost = 0 if a[a_index - 1] == b[b_index - 1] else 1
            matrix[a_index][b_index] = min(
                matrix[a_index - 1][b_index] + 1,
                matrix[a_index][b_index - 1] + 1,
                matrix[a_index - 1][b_index - 1] + cost,
            )
    return matrix[len(a)][len(b)]


def levenshtein_ratio(a: str, b: str) -> float:
    """Similarity ratio in [0, 1] derived from Levenshtein distance."""
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    distance = levenshtein_distance(a, b)
    return 1 - (distance / max_len)


def _slice_lines(content: str, original_lines: list[str], start_line: int, end_line: int) -> str:
    match_start_index = 0
    for line_index in range(start_line):
        match_start_index += len(original_lines[line_index]) + 1

    match_end_index = match_start_index
    for line_index in range(start_line, end_line + 1):
        match_end_index += len(original_lines[line_index])
        if line_index < end_line:
            match_end_index += 1
    return content[match_start_index:match_end_index]


def LineTrimmedReplacer(_content: str, _find: str) -> Generator[str, None, None]:  # noqa: N802
    content = _content
    find = _find
    original_lines = content.split("\n")
    search_lines = find.split("\n")

    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    for index in range(0, len(original_lines) - len(search_lines) + 1):
        matches = True
        for offset in range(len(search_lines)):
            original_trimmed = original_lines[index + offset].strip()
            search_trimmed = search_lines[offset].strip()
            if original_trimmed != search_trimmed:
                matches = False
                break

        if not matches:
            continue

        match_start_index = 0
        for line_index in range(index):
            match_start_index += len(original_lines[line_index]) + 1

        match_end_index = match_start_index
        for line_index in range(len(search_lines)):
            match_end_index += len(original_lines[index + line_index])
            if line_index < len(search_lines) - 1:
                match_end_index += 1

        yield content[match_start_index:match_end_index]


def BlockAnchorReplacer(_content: str, _find: str) -> Generator[str, None, None]:  # noqa: N802
    content = _content
    find = _find
    original_lines = content.split("\n")
    search_lines = find.split("\n")

    if len(search_lines) < 3:
        return

    if search_lines[-1] == "":
        search_lines.pop()

    first_line_search = search_lines[0].strip()
    last_line_search = search_lines[-1].strip()
    search_block_size = len(search_lines)

    candidates: list[tuple[int, int]] = []
    for start_line in range(len(original_lines)):
        if original_lines[start_line].strip() != first_line_search:
            continue
        for end_line in range(start_line + 2, len(original_lines)):
            if original_lines[end_line].strip() == last_line_search:
                candidates.append((start_line, end_line))
                break

    if len(candidates) == 0:
        return

    if len(candidates) == 1:
        start_line, end_line = candidates[0]
        actual_block_size = end_line - start_line + 1
        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_block_size - 2)

        if lines_to_check > 0:
            for line_index in range(1, min(search_block_size - 1, actual_block_size - 1)):
                original_line = original_lines[start_line + line_index].strip()
                search_line = search_lines[line_index].strip()
                max_len = max(len(original_line), len(search_line))
                if max_len == 0:
                    continue
                distance = levenshtein_distance(original_line, search_line)
                similarity += (1 - distance / max_len) / lines_to_check
                if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
                    break
        else:
            similarity = 1.0

        if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
            yield _slice_lines(content, original_lines, start_line, end_line)
        return

    best_match: tuple[int, int] | None = None
    max_similarity = -1.0
    for candidate_start, candidate_end in candidates:
        actual_block_size = candidate_end - candidate_start + 1
        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_block_size - 2)

        if lines_to_check > 0:
            for line_index in range(1, min(search_block_size - 1, actual_block_size - 1)):
                original_line = original_lines[candidate_start + line_index].strip()
                search_line = search_lines[line_index].strip()
                max_len = max(len(original_line), len(search_line))
                if max_len == 0:
                    continue
                distance = levenshtein_distance(original_line, search_line)
                similarity += 1 - distance / max_len
            similarity /= lines_to_check
        else:
            similarity = 1.0

        if similarity > max_similarity:
            max_similarity = similarity
            best_match = (candidate_start, candidate_end)

    if max_similarity >= MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD and best_match is not None:
        start_line, end_line = best_match
        yield _slice_lines(content, original_lines, start_line, end_line)


def WhitespaceNormalizedReplacer(  # noqa: N802
    _content: str,
    _find: str,
) -> Generator[str, None, None]:
    content = _content
    find = _find

    def normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    normalized_find = normalize_whitespace(find)
    lines = content.split("\n")

    for line in lines:
        if normalize_whitespace(line) == normalized_find:
            yield line
            continue

        normalized_line = normalize_whitespace(line)
        if normalized_find and normalized_find in normalized_line:
            words = re.split(r"\s+", find.strip())
            if words:
                pattern = r"\s+".join(re.escape(word) for word in words)
                try:
                    match = re.search(pattern, line)
                except re.error:
                    match = None
                if match is not None:
                    yield match.group(0)

    find_lines = find.split("\n")
    if len(find_lines) > 1:
        for index in range(0, len(lines) - len(find_lines) + 1):
            block = lines[index : index + len(find_lines)]
            if normalize_whitespace("\n".join(block)) == normalized_find:
                yield "\n".join(block)


def IndentationFlexibleReplacer(  # noqa: N802
    _content: str,
    _find: str,
) -> Generator[str, None, None]:
    content = _content
    find = _find

    def remove_indentation(text: str) -> str:
        lines = text.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]
        if len(non_empty_lines) == 0:
            return text

        def leading_whitespace_count(line: str) -> int:
            match = re.match(r"^(\s*)", line)
            if match is None:
                return 0
            return len(match.group(1))

        min_indent = min(leading_whitespace_count(line) for line in non_empty_lines)
        return "\n".join(line if not line.strip() else line[min_indent:] for line in lines)

    normalized_find = remove_indentation(find)
    content_lines = content.split("\n")
    find_lines = find.split("\n")

    for index in range(0, len(content_lines) - len(find_lines) + 1):
        block = "\n".join(content_lines[index : index + len(find_lines)])
        if remove_indentation(block) == normalized_find:
            yield block


def EscapeNormalizedReplacer(_content: str, _find: str) -> Generator[str, None, None]:  # noqa: N802
    content = _content
    find = _find

    def unescape_string(value: str) -> str:
        pattern = re.compile(r"""\\(n|t|r|'|"|`|\\|\$)|\\\n""")

        def _replace(match: re.Match[str]) -> str:
            token = match.group(1)
            if token is None:
                return "\n"
            mapping = {
                "n": "\n",
                "t": "\t",
                "r": "\r",
                "'": "'",
                '"': '"',
                "`": "`",
                "\\": "\\",
                "$": "$",
            }
            return mapping.get(token, match.group(0))

        return pattern.sub(_replace, value)

    unescaped_find = unescape_string(find)
    if unescaped_find in content:
        yield unescaped_find

    lines = content.split("\n")
    find_lines = unescaped_find.split("\n")
    for index in range(0, len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[index : index + len(find_lines)])
        if unescape_string(block) == unescaped_find:
            yield block


def TrimmedBoundaryReplacer(_content: str, _find: str) -> Generator[str, None, None]:  # noqa: N802
    content = _content
    find = _find
    trimmed_find = find.strip()
    if trimmed_find == find:
        return

    if trimmed_find in content:
        yield trimmed_find

    lines = content.split("\n")
    find_lines = find.split("\n")
    for index in range(0, len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[index : index + len(find_lines)])
        if block.strip() == trimmed_find:
            yield block


def ContextAwareReplacer(_content: str, _find: str) -> Generator[str, None, None]:  # noqa: N802
    content = _content
    find = _find
    find_lines = find.split("\n")
    if len(find_lines) < 3:
        return
    if find_lines[-1] == "":
        find_lines.pop()

    content_lines = content.split("\n")
    first_line = find_lines[0].strip()
    last_line = find_lines[-1].strip()

    for start_index in range(len(content_lines)):
        if content_lines[start_index].strip() != first_line:
            continue
        for end_index in range(start_index + 2, len(content_lines)):
            if content_lines[end_index].strip() != last_line:
                continue
            block_lines = content_lines[start_index : end_index + 1]
            block = "\n".join(block_lines)
            if len(block_lines) == len(find_lines):
                matching_lines = 0
                total_non_empty_lines = 0
                for line_index in range(1, len(block_lines) - 1):
                    block_line = block_lines[line_index].strip()
                    find_line = find_lines[line_index].strip()
                    if block_line or find_line:
                        total_non_empty_lines += 1
                        if block_line == find_line:
                            matching_lines += 1
                if total_non_empty_lines == 0 or (matching_lines / total_non_empty_lines) >= 0.5:
                    yield block
                    break
            break


def trim_diff(diff: str) -> str:
    """Trim common indentation from unified diff content lines."""
    lines = diff.split("\n")
    content_lines = [
        line
        for line in lines
        if (line.startswith("+") or line.startswith("-") or line.startswith(" "))
        and not line.startswith("---")
        and not line.startswith("+++")
    ]
    if len(content_lines) == 0:
        return diff

    minimum_indent = None
    for line in content_lines:
        content = line[1:]
        if content.strip():
            match = re.match(r"^(\s*)", content)
            indent = len(match.group(1)) if match is not None else 0
            if minimum_indent is None or indent < minimum_indent:
                minimum_indent = indent

    if minimum_indent is None or minimum_indent == 0:
        return diff

    trimmed_lines = []
    for line in lines:
        is_content = line.startswith("+") or line.startswith("-") or line.startswith(" ")
        if is_content and not line.startswith("---") and not line.startswith("+++"):
            trimmed_lines.append(line[0] + line[1 + minimum_indent :])
        else:
            trimmed_lines.append(line)
    return "\n".join(trimmed_lines)


def MultiOccurrenceReplacer(content: str, find: str) -> Generator[str, None, None]:  # noqa: N802
    start_index = 0
    while True:
        index = content.find(find, start_index)
        if index == -1:
            break
        yield find
        start_index = index + len(find)


def replace(content: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Apply replacement using ordered replacer strategies."""
    if old_string == new_string:
        raise ValueError("No changes to apply: oldString and newString are identical.")

    not_found = True
    replacers: tuple[Replacer, ...] = (
        SimpleReplacer,
        LineTrimmedReplacer,
        BlockAnchorReplacer,
        WhitespaceNormalizedReplacer,
        IndentationFlexibleReplacer,
        EscapeNormalizedReplacer,
        TrimmedBoundaryReplacer,
        ContextAwareReplacer,
        MultiOccurrenceReplacer,
    )
    for replacer in replacers:
        for search in replacer(content, old_string):
            index = content.find(search)
            if index == -1:
                continue
            not_found = False
            if replace_all:
                return content.replace(search, new_string)
            last_index = content.rfind(search)
            if index != last_index:
                continue
            return content[:index] + new_string + content[index + len(search) :]

    if not_found:
        raise ValueError(
            "Could not find oldString in the file. It must match exactly, including whitespace, "
            "indentation, and line endings."
        )
    raise ValueError(
        "Found multiple matches for oldString. "
        "Provide more surrounding context to make the match unique."
    )


class EditParams(BaseModel):
    """Parameters for edit tool."""

    model_config = ConfigDict(extra="forbid")
    file_path: str
    old_string: str
    new_string: str
    replace_all: bool = False


def _resolve_path(file_path: str, base_directory: Path) -> Path:
    candidate = Path(file_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_directory / candidate).resolve()


def _resolve_workspace(ctx: ToolContext) -> tuple[Path, str]:
    base_directory = Path(".").resolve()
    worktree = "/"
    if not isinstance(ctx.extra, dict):
        return base_directory, worktree

    directory = ctx.extra.get("directory")
    if isinstance(directory, str) and directory.strip():
        base_directory = Path(directory).resolve()

    worktree_input = ctx.extra.get("worktree")
    if isinstance(worktree_input, str) and worktree_input.strip():
        worktree = worktree_input
    return base_directory, worktree


def _permission_pattern(target: Path, base_directory: Path, worktree: str) -> str:
    if worktree != "/":
        try:
            return str(target.relative_to(Path(worktree).resolve()))
        except ValueError:
            return str(target)
    try:
        return str(target.relative_to(base_directory))
    except ValueError:
        return str(target)


def _build_diff(path_text: str, old_content: str, new_content: str) -> str:
    lines = unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=path_text,
        tofile=path_text,
        lineterm="",
    )
    return trim_diff("\n".join(lines))


async def _execute_edit(params: EditParams, ctx: ToolContext) -> ToolResult:
    if params.old_string == params.new_string:
        raise ValueError("No changes to apply: oldString and newString are identical.")

    base_directory, worktree = _resolve_workspace(ctx)
    target = _resolve_path(params.file_path, base_directory)
    if not contains_path(directory=str(base_directory), worktree=worktree, filepath=str(target)):
        await ctx.ask("external_directory", [str(target.parent)])

    existed = target.exists()
    old_content = target.read_text(encoding="utf-8") if existed else ""
    line_ending = detect_line_ending(old_content)
    normalized_old = normalize_line_endings(old_content)
    normalized_new_string = normalize_line_endings(params.new_string)
    if params.old_string == "":
        normalized_new = normalized_new_string
    else:
        normalized_new = replace(
            normalized_old,
            normalize_line_endings(params.old_string),
            normalized_new_string,
            replace_all=params.replace_all,
        )
    new_content = convert_to_line_ending(normalized_new, line_ending)

    diff = _build_diff(str(target), old_content, new_content)
    pattern = _permission_pattern(target, base_directory, worktree)
    await ctx.ask("edit", [pattern])
    ctx.metadata({"filepath": str(target), "diff": diff})

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")

    return ToolResult(
        title=pattern,
        output="Edited file successfully.",
        metadata={"path": str(target), "exists": existed, "diff": diff},
    )


def create_edit_tool() -> ToolInfo[EditParams]:
    """Create edit tool definition."""
    return define(
        "edit",
        "Replace text in a file with robust matching strategies.",
        EditParams,
        _execute_edit,
    )
