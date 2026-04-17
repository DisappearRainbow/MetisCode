import os

from metiscode.permission import Rule, disabled, evaluate, from_config, merge


def _rule(permission: str, pattern: str, action: str) -> Rule:
    return Rule(permission=permission, pattern=pattern, action=action)  # type: ignore[arg-type]


def test_from_config_string_and_object_values() -> None:
    rules = from_config(
        {
            "bash": {"*": "allow", "rm": "deny"},
            "edit": "allow",
            "webfetch": "ask",
        }
    )
    assert rules == [
        _rule("bash", "*", "allow"),
        _rule("bash", "rm", "deny"),
        _rule("edit", "*", "allow"),
        _rule("webfetch", "*", "ask"),
    ]


def test_from_config_expands_home() -> None:
    home = os.path.expanduser("~")
    rules = from_config(
        {
            "external_directory": {
                "~/projects/*": "allow",
                "$HOME": "deny",
                "/some/~/path": "ask",
            }
        }
    )
    assert rules == [
        _rule("external_directory", f"{home}/projects/*", "allow"),
        _rule("external_directory", home, "deny"),
        _rule("external_directory", "/some/~/path", "ask"),
    ]


def test_merge_concatenates_and_order_preserved() -> None:
    merged = merge(
        [_rule("bash", "*", "allow")],
        [_rule("bash", "rm", "ask")],
        [_rule("edit", "*", "deny")],
    )
    assert merged == [
        _rule("bash", "*", "allow"),
        _rule("bash", "rm", "ask"),
        _rule("edit", "*", "deny"),
    ]


def test_evaluate_last_matching_rule_wins() -> None:
    rules = [
        _rule("bash", "*", "allow"),
        _rule("bash", "rm", "deny"),
    ]
    assert evaluate("bash", "rm", rules).action == "deny"
    reverse_rules = [
        _rule("bash", "rm", "deny"),
        _rule("bash", "*", "allow"),
    ]
    assert evaluate("bash", "rm", reverse_rules).action == "allow"
    assert evaluate("unknown_tool", "anything", rules).action == "ask"


def test_evaluate_task_wildcards() -> None:
    rules = [
        _rule("task", "orchestrator-*", "deny"),
        _rule("task", "orchestrator-fast", "allow"),
    ]
    assert evaluate("task", "orchestrator-fast", rules).action == "allow"
    assert evaluate("task", "orchestrator-slow", rules).action == "deny"
    assert evaluate("task", "general", rules).action == "ask"


def test_disabled_task_tool_follows_last_permission_match() -> None:
    deny_all = [_rule("task", "*", "deny")]
    assert "task" in disabled(["task"], deny_all)

    specific_only = [_rule("task", "orchestrator-*", "deny")]
    assert "task" not in disabled(["task"], specific_only)

    wildcard_deny_then_specific_allow = [
        _rule("task", "*", "deny"),
        _rule("task", "orchestrator-coder", "allow"),
    ]
    assert "task" not in disabled(["task"], wildcard_deny_then_specific_allow)
