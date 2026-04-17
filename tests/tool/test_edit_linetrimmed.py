from metiscode.tool.edit import replace


def test_line_trimmed_replacer_matches_indentation_difference() -> None:
    content = "alpha\n    beta\ngamma"
    result = replace(content, "alpha\nbeta\ngamma", "A\nB\nC")
    assert result == "A\nB\nC"


def test_line_trimmed_replacer_matches_tabs_vs_spaces() -> None:
    content = "start\n\tvalue = 1\nend"
    result = replace(content, "start\n    value = 1\nend", "start\nvalue = 2\nend")
    assert result == "start\nvalue = 2\nend"


def test_line_trimmed_replacer_handles_multiline_block() -> None:
    content = "x\n  y\n  z\nw\n"
    result = replace(content, "x\ny\nz", "X\nY\nZ")
    assert result == "X\nY\nZ\nw\n"


def test_line_trimmed_replacer_does_not_match_different_text() -> None:
    try:
        _ = replace("a\n b\nc", "a\nb\nx", "replaced")
    except ValueError as error:
        assert "Could not find oldString" in str(error)
    else:
        raise AssertionError("Expected ValueError for non-matching line-trimmed search")

