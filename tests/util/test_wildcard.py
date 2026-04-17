import sys

from metiscode.util import wildcard


def test_match_handles_glob_tokens() -> None:
    assert wildcard.match("file1.txt", "file?.txt")
    assert not wildcard.match("file12.txt", "file?.txt")
    assert wildcard.match("foo+bar", "foo+bar")


def test_match_trailing_space_wildcard() -> None:
    assert wildcard.match("ls", "ls *")
    assert wildcard.match("ls -la", "ls *")
    assert wildcard.match("ls foo bar", "ls *")
    assert wildcard.match("ls", "ls*")
    assert wildcard.match("lstmeval", "ls*")
    assert not wildcard.match("lstmeval", "ls *")
    assert wildcard.match("git status", "git *")
    assert wildcard.match("git", "git *")
    assert wildcard.match("git commit -m foo", "git *")


def test_all_picks_most_specific_pattern() -> None:
    rules = {"*": "deny", "git *": "ask", "git status": "allow"}
    assert wildcard.all_matches("git status", rules) == "allow"
    assert wildcard.all_matches("git log", rules) == "ask"
    assert wildcard.all_matches("echo hi", rules) == "deny"


def test_all_structured_matches_command_sequences() -> None:
    rules = {"git *": "ask", "git status*": "allow"}
    assert wildcard.all_structured({"head": "git", "tail": ["status", "--short"]}, rules) == "allow"
    assert (
        wildcard.all_structured(
            {"head": "npm", "tail": ["run", "build", "--watch"]},
            {"npm run *": "allow"},
        )
        == "allow"
    )
    assert wildcard.all_structured({"head": "ls", "tail": ["-la"]}, rules) is None


def test_match_normalizes_slashes_and_windows_case() -> None:
    assert wildcard.match(r"C:\Windows\System32\*", "C:/Windows/System32/*")
    assert wildcard.match("C:/Windows/System32/drivers", r"C:\Windows\System32\*")
    if sys.platform == "win32":
        assert wildcard.match(r"C:\windows\system32\hosts", "C:/Windows/System32/*")
        assert wildcard.match("c:/windows/system32/hosts", r"C:\Windows\System32\*")
    else:
        assert not wildcard.match("/users/test/file", "/Users/test/*")

