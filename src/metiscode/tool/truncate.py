"""Tool output truncation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from metiscode.util.ids import ulid_str

MAX_CHARS = 80_000
TRUNCATION_DIR = Path.home() / ".metiscode" / "tmp"
FALLBACK_TRUNCATION_DIR = Path(".metiscode") / "tmp"


@dataclass(slots=True, frozen=True)
class TruncateResult:
    """Truncation result payload."""

    truncated: bool
    output: str
    overflow_path: str | None


def truncate_output(
    text: str,
    max_chars: int = MAX_CHARS,
    *,
    overflow_dir: Path | None = None,
) -> TruncateResult:
    """Truncate large output and persist full content to overflow file."""
    if len(text) <= max_chars:
        return TruncateResult(truncated=False, output=text, overflow_path=None)

    target_dir = overflow_dir or TRUNCATION_DIR
    overflow_file: Path | None = None
    for candidate in (target_dir, FALLBACK_TRUNCATION_DIR):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            current = candidate / f"{ulid_str()}.txt"
            current.write_text(text, encoding="utf-8")
            overflow_file = current
            break
        except OSError:
            continue
    if overflow_file is None:
        clipped = text[:max_chars]
        output = f"{clipped}\n\n...output truncated..."
        return TruncateResult(truncated=True, output=output, overflow_path=None)

    clipped = text[:max_chars]
    output = f"{clipped}\n\n...output truncated...\nFull output saved to: {overflow_file}"
    return TruncateResult(truncated=True, output=output, overflow_path=str(overflow_file))
