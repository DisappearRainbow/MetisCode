from metiscode.agent import AgentService


def _has_rule(agent, permission: str, pattern: str, action: str) -> bool:  # type: ignore[no-untyped-def]
    return any(
        rule.permission == permission and rule.pattern == pattern and rule.action == action
        for rule in agent.permission
    )


def test_get_build_contains_expected_permission_rules() -> None:
    service = AgentService()
    build = service.get("build")
    assert _has_rule(build, "question", "*", "allow")
    assert _has_rule(build, "plan_enter", "*", "allow")


def test_plan_agent_denies_edit_except_plans_path() -> None:
    service = AgentService()
    plan = service.get("plan")
    assert _has_rule(plan, "edit", "*", "deny")
    assert _has_rule(plan, "edit", "plans/*", "allow")


def test_override_model_applies_to_build_agent() -> None:
    service = AgentService(overrides={"build": {"model": "openai:gpt-4.1"}})
    build = service.get("build")
    assert build.model == "openai:gpt-4.1"


def test_default_agent_is_build() -> None:
    service = AgentService()
    default_agent = service.default_agent()
    assert default_agent.name == "build"


def test_list_excludes_hidden_agents() -> None:
    service = AgentService()
    listed_names = [agent.name for agent in service.list()]
    assert "compaction" not in listed_names
    assert "title" not in listed_names
    assert "summary" not in listed_names

