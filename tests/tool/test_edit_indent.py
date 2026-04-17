from metiscode.tool.edit import replace


def test_indentation_flexible_replacer_matches_different_indent_levels() -> None:
    content = "if x:\n        do_thing()\n        end()"
    result = replace(content, "if x:\n    do_thing()\n    end()", "if x:\n    done()")
    assert result == "if x:\n    done()"


def test_indentation_flexible_replacer_matches_tabs_vs_spaces() -> None:
    content = "root\n\tchild\n\tleaf"
    result = replace(content, "root\n    child\n    leaf", "root\nchild2\nleaf2")
    assert result == "root\nchild2\nleaf2"


def test_indentation_flexible_replacer_raises_when_structure_differs() -> None:
    try:
        _ = replace("a\n  b\n  c", "a\n b\n x", "replace")
    except ValueError as error:
        assert "Could not find oldString" in str(error)
    else:
        raise AssertionError("Expected ValueError for non-matching indentation-flexible search")

