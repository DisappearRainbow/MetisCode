import os

import pytest

from metiscode.provider import ProviderService, ProviderUnknownError


def test_parse_model_with_colon() -> None:
    service = ProviderService()
    ref = service.parse_model("openai:gpt-4.1")
    assert ref.provider_id == "openai"
    assert ref.model_id == "gpt-4.1"
    assert ref.canonical == "openai:gpt-4.1"


def test_parse_model_with_slash() -> None:
    service = ProviderService()
    ref = service.parse_model("anthropic/claude-3-5-sonnet")
    assert ref.provider_id == "anthropic"
    assert ref.model_id == "claude-3-5-sonnet"


def test_parse_model_without_provider_uses_default() -> None:
    service = ProviderService()
    ref = service.parse_model("claude-sonnet-4-5", default_provider="anthropic")
    assert ref.provider_id == "anthropic"
    assert ref.model_id == "claude-sonnet-4-5"


def test_unknown_provider_raises() -> None:
    service = ProviderService()
    with pytest.raises(ProviderUnknownError):
        service.parse_model("unknown:model-a")


def test_resolve_options_deepseek_defaults_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ProviderService()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    ref = service.parse_model("deepseek:deepseek-chat")

    options = service.resolve_options(ref)
    assert options["api_key"] == "sk-test"
    assert options["base_url"] == "https://api.deepseek.com/v1"

    overridden = service.resolve_options(ref, provider_options={"base_url": "https://proxy.local/v1"})
    assert overridden["base_url"] == "https://proxy.local/v1"


def test_resolve_options_without_env_keeps_known_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ProviderService()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ref = service.parse_model("openai:gpt-4.1")

    options = service.resolve_options(ref)
    assert "api_key" not in options
    assert "base_url" not in options
    assert os.getenv("OPENAI_API_KEY") is None

