from metiscode.tool.edit import replace


def test_escape_normalized_replacer_matches_escaped_newline() -> None:
    content = "start\nline2\nend"
    result = replace(content, "start\\nline2\\nend", "done")
    assert result == "done"


def test_escape_normalized_replacer_matches_escaped_tab() -> None:
    content = "key\tvalue"
    result = replace(content, "key\\tvalue", "key value")
    assert result == "key value"


def test_escape_normalized_replacer_matches_escaped_quotes() -> None:
    content = 'print("hello")'
    result = replace(content, 'print(\\"hello\\")', "ok")
    assert result == "ok"


def test_escape_normalized_replacer_raises_when_not_found() -> None:
    try:
        _ = replace("alpha\\nbeta", "alpha\\tgamma", "x")
    except ValueError as error:
        assert "Could not find oldString" in str(error)
    else:
        raise AssertionError("Expected ValueError for unmatched escaped search")

