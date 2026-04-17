from metiscode.tool.edit import TrimmedBoundaryReplacer, replace


def test_trimmed_boundary_replacer_matches_trimmed_single_line() -> None:
    result = replace("value", "  value  ", "updated")
    assert result == "updated"


def test_trimmed_boundary_replacer_matches_trimmed_multiline_block() -> None:
    content = "head\nmiddle\ntail"
    result = replace(content, "  head\nmiddle\ntail  ", "replaced")
    assert result == "replaced"


def test_trimmed_boundary_replacer_returns_empty_for_already_trimmed_find() -> None:
    matches = list(TrimmedBoundaryReplacer("a\nb", "a\nb"))
    assert matches == []

