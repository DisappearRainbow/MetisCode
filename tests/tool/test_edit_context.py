from metiscode.tool.edit import ContextAwareReplacer, replace, trim_diff


def test_context_aware_replacer_matches_with_partial_middle_similarity() -> None:
    content = "start\nalpha\nbeta\nend\n"
    result = replace(content, "start\nalpha\nzeta\nend", "ok")
    assert result == "ok\n"


def test_context_aware_replacer_requires_three_lines() -> None:
    matches = list(ContextAwareReplacer("a\nb\nc", "a\nb"))
    assert matches == []


def test_context_aware_replacer_returns_empty_without_anchor_pair() -> None:
    matches = list(ContextAwareReplacer("x\ny\nz", "start\nmid\nend"))
    assert matches == []


def test_trim_diff_removes_common_indentation_in_diff_lines() -> None:
    diff = "\n".join(
        [
            "--- a.py",
            "+++ a.py",
            "@@ -1,2 +1,2 @@",
            "-    old()",
            "+    new()",
            "     keep()",
        ]
    )
    trimmed = trim_diff(diff)
    assert "-old()" in trimmed
    assert "+new()" in trimmed
    assert " keep()" in trimmed


def test_trim_diff_returns_original_when_no_content_lines() -> None:
    diff = "--- a.py\n+++ a.py"
    assert trim_diff(diff) == diff


def test_trim_diff_returns_original_when_min_indent_zero() -> None:
    diff = "\n".join(
        [
            "--- a.py",
            "+++ a.py",
            "@@ -1,1 +1,1 @@",
            "-old()",
            "+new()",
        ]
    )
    assert trim_diff(diff) == diff

