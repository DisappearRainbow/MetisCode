from metiscode.tool.edit import replace


def test_replace_simple_occurrence() -> None:
    result = replace("hello world", "hello", "hi")
    assert result == "hi world"


def test_replace_all_replaces_every_occurrence() -> None:
    result = replace("a b a b", "a", "x", replace_all=True)
    assert result == "x b x b"


def test_replace_rejects_identical_old_and_new() -> None:
    try:
        _ = replace("hello", "hello", "hello")
    except ValueError as error:
        assert "identical" in str(error)
    else:
        raise AssertionError("Expected ValueError for identical old/new strings")


def test_replace_raises_when_old_string_not_found() -> None:
    try:
        _ = replace("hello world", "missing", "x")
    except ValueError as error:
        assert "Could not find oldString" in str(error)
    else:
        raise AssertionError("Expected ValueError when oldString is missing")


def test_replace_raises_when_multiple_matches_and_not_replace_all() -> None:
    try:
        _ = replace("foo foo", "foo", "bar")
    except ValueError as error:
        assert "multiple matches" in str(error)
    else:
        raise AssertionError("Expected ValueError when match is ambiguous")

