import pytest

from metiscode.provider import ProviderService, ProviderUnknownError


def test_parse_model_returns_expected_reference() -> None:
    service = ProviderService()
    ref = service.parse_model("anthropic:claude-sonnet-4-20250514")
    assert ref.provider_id == "anthropic"
    assert ref.model_id == "claude-sonnet-4-20250514"


def test_get_model_returns_expected_context_limit() -> None:
    service = ProviderService()
    model = service.get_model("anthropic", "claude-sonnet-4-20250514")
    assert model.context_limit == 200_000


def test_default_model_returns_anthropic_sonnet() -> None:
    service = ProviderService()
    provider, model = service.default_model()
    assert provider.id == "anthropic"
    assert model.id == "claude-sonnet-4-20250514"


def test_get_provider_unknown_raises() -> None:
    service = ProviderService()
    with pytest.raises(ProviderUnknownError):
        service.get_provider("unknown")

