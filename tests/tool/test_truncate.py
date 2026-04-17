import tempfile
from pathlib import Path

from metiscode.tool.truncate import truncate_output


def _writable_tmp_dir() -> Path:
    base = Path(".tmp_truncate")
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="metiscode-truncate-", dir=base))


def test_short_text_not_truncated() -> None:
    result = truncate_output("hello", max_chars=100)
    assert result.truncated is False
    assert result.output == "hello"
    assert result.overflow_path is None


def test_long_text_truncated_and_overflow_path_created() -> None:
    overflow_dir = _writable_tmp_dir()
    long_text = "x" * 200_000
    result = truncate_output(long_text, max_chars=1000, overflow_dir=overflow_dir)

    assert result.truncated is True
    assert "...output truncated..." in result.output
    assert result.overflow_path is not None
    assert Path(result.overflow_path).exists()


def test_overflow_file_contains_full_content() -> None:
    overflow_dir = _writable_tmp_dir()
    long_text = "line\n" * 50_000
    result = truncate_output(long_text, max_chars=500, overflow_dir=overflow_dir)

    assert result.overflow_path is not None
    saved = Path(result.overflow_path).read_text(encoding="utf-8")
    assert saved == long_text
