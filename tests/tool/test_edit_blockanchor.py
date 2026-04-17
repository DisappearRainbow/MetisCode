from metiscode.tool.edit import BlockAnchorReplacer, levenshtein_distance, replace


def test_block_anchor_single_candidate_matches_on_anchors() -> None:
    content = "first\nmiddle line\nlast\n"
    result = replace(content, "first\nmiddle typo\nlast", "A\nB\nC")
    assert result == "A\nB\nC\n"


def test_block_anchor_multiple_candidates_chooses_best_similarity() -> None:
    content = "start\napple\nend\n\nstart\ntarget line\nend\n"
    old = "start\ntargat line\nend"
    result = replace(content, old, "start\nupdated\nend")
    assert result == "start\napple\nend\n\nstart\nupdated\nend\n"


def test_block_anchor_replacer_ignores_search_shorter_than_three_lines() -> None:
    matches = list(BlockAnchorReplacer("a\nb\nc", "a\nb"))
    assert matches == []


def test_block_anchor_replacer_returns_empty_when_anchors_not_found() -> None:
    matches = list(BlockAnchorReplacer("x\ny\nz\n", "start\nmiddle\nend"))
    assert matches == []


def test_levenshtein_distance_kitten_sitting() -> None:
    assert levenshtein_distance("kitten", "sitting") == 3

