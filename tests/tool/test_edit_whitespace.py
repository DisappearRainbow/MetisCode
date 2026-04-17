from metiscode.tool.edit import replace


def test_whitespace_normalized_replacer_matches_collapsed_spaces() -> None:
    result = replace("foo bar", "foo  bar", "baz")
    assert result == "baz"


def test_whitespace_normalized_replacer_matches_tab_and_space() -> None:
    result = replace("value\t=\t1", "value = 1", "value = 2")
    assert result == "value = 2"


def test_whitespace_normalized_replacer_matches_multiline_blocks() -> None:
    content = "a\n  b   c\n\td\ne"
    result = replace(content, "a\nb c\nd", "A\nBC\nD")
    assert result == "A\nBC\nD\ne"


def test_whitespace_normalized_replacer_raises_when_not_found() -> None:
    try:
        _ = replace("alpha beta", "alpha gamma", "x")
    except ValueError as error:
        assert "Could not find oldString" in str(error)
    else:
        raise AssertionError("Expected ValueError for unmatched whitespace-normalized search")

