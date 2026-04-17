"""Provider service for model id parsing and SDK option resolution."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict

from metiscode.util.errors import MetiscodeError

KnownProvider = Literal["anthropic", "openai", "deepseek"]


class ProviderUnknownError(MetiscodeError):
    """Raised when provider id is not registered."""

    def __init__(self, provider_id: str) -> None:
        super().__init__(f"Unknown provider: {provider_id}")
        self.provider_id = provider_id


class ProviderInfo(BaseModel):
    """Static provider metadata."""

    model_config = ConfigDict(extra="forbid")
    id: KnownProvider
    name: str = ""
    api_key_env: str
    base_url: str | None = None
    sdk_family: Literal["anthropic", "openai"]


class ModelInfo(BaseModel):
    """Static model metadata."""

    model_config = ConfigDict(extra="forbid")
    id: str
    provider_id: KnownProvider
    name: str
    context_limit: int
    output_limit: int
    supports_reasoning: bool = False
    supports_images: bool = False
    supports_temperature: bool = True


class ModelRef(BaseModel):
    """Normalized model reference."""

    model_config = ConfigDict(extra="forbid")
    provider_id: KnownProvider
    model_id: str
    raw: str

    @property
    def canonical(self) -> str:
        """Canonical model reference for user display."""
        return f"{self.provider_id}:{self.model_id}"


class ProviderService:
    """Minimal provider registry and resolver for v1."""

    def __init__(self) -> None:
        self._providers: dict[KnownProvider, ProviderInfo] = {
            "anthropic": ProviderInfo(
                id="anthropic",
                name="Anthropic",
                api_key_env="ANTHROPIC_API_KEY",
                sdk_family="anthropic",
            ),
            "openai": ProviderInfo(
                id="openai",
                name="OpenAI",
                api_key_env="OPENAI_API_KEY",
                sdk_family="openai",
            ),
            "deepseek": ProviderInfo(
                id="deepseek",
                name="DeepSeek",
                api_key_env="DEEPSEEK_API_KEY",
                base_url="https://api.deepseek.com/v1",
                sdk_family="openai",
            ),
        }
        self._models: dict[KnownProvider, dict[str, ModelInfo]] = {
            "anthropic": {
                "claude-sonnet-4-20250514": ModelInfo(
                    id="claude-sonnet-4-20250514",
                    provider_id="anthropic",
                    name="Claude Sonnet 4",
                    context_limit=200_000,
                    output_limit=8_192,
                    supports_reasoning=True,
                ),
                "claude-opus-4-20250514": ModelInfo(
                    id="claude-opus-4-20250514",
                    provider_id="anthropic",
                    name="Claude Opus 4",
                    context_limit=200_000,
                    output_limit=8_192,
                    supports_reasoning=True,
                ),
                "claude-haiku-3.5": ModelInfo(
                    id="claude-haiku-3.5",
                    provider_id="anthropic",
                    name="Claude Haiku 3.5",
                    context_limit=200_000,
                    output_limit=8_192,
                ),
            },
            "openai": {
                "gpt-4.1": ModelInfo(
                    id="gpt-4.1",
                    provider_id="openai",
                    name="GPT-4.1",
                    context_limit=128_000,
                    output_limit=16_384,
                ),
                "gpt-4.1-mini": ModelInfo(
                    id="gpt-4.1-mini",
                    provider_id="openai",
                    name="GPT-4.1 mini",
                    context_limit=128_000,
                    output_limit=16_384,
                ),
                "o3": ModelInfo(
                    id="o3",
                    provider_id="openai",
                    name="o3",
                    context_limit=200_000,
                    output_limit=16_384,
                    supports_reasoning=True,
                    supports_temperature=False,
                ),
                "o4-mini": ModelInfo(
                    id="o4-mini",
                    provider_id="openai",
                    name="o4-mini",
                    context_limit=200_000,
                    output_limit=16_384,
                    supports_reasoning=True,
                    supports_temperature=False,
                ),
            },
            "deepseek": {
                "deepseek-chat": ModelInfo(
                    id="deepseek-chat",
                    provider_id="deepseek",
                    name="DeepSeek Chat",
                    context_limit=64_000,
                    output_limit=8_192,
                ),
                "deepseek-reasoner": ModelInfo(
                    id="deepseek-reasoner",
                    provider_id="deepseek",
                    name="DeepSeek Reasoner",
                    context_limit=64_000,
                    output_limit=8_192,
                    supports_reasoning=True,
                    supports_temperature=False,
                ),
            },
        }

    def provider(self, provider_id: str) -> ProviderInfo:
        """Get provider metadata."""
        normalized = provider_id.strip().lower()
        if normalized not in self._providers:
            raise ProviderUnknownError(normalized)
        return self._providers[normalized]

    def get_provider(self, provider_id: str) -> ProviderInfo:
        """Compatibility alias for provider()."""
        return self.provider(provider_id)

    def get_model(self, provider_id: str, model_id: str) -> ModelInfo:
        """Fetch model metadata by provider/model id."""
        provider = self.provider(provider_id)
        models = self._models[provider.id]
        if model_id not in models:
            raise ValueError(f"Unknown model for provider {provider.id}: {model_id}")
        return models[model_id]

    def default_model(self) -> tuple[ProviderInfo, ModelInfo]:
        """Return default provider/model pair."""
        provider = self.provider("anthropic")
        model = self.get_model("anthropic", "claude-sonnet-4-20250514")
        return provider, model

    def parse_model(self, model: str, *, default_provider: KnownProvider = "anthropic") -> ModelRef:
        """Parse model refs in `provider:model`, `provider/model`, or bare model forms."""
        value = model.strip()
        if ":" in value:
            provider_text, model_id = value.split(":", 1)
            provider_info = self.provider(provider_text)
            return ModelRef(provider_id=provider_info.id, model_id=model_id.strip(), raw=model)
        if "/" in value:
            provider_text, model_id = value.split("/", 1)
            provider_info = self.provider(provider_text)
            return ModelRef(provider_id=provider_info.id, model_id=model_id.strip(), raw=model)
        provider_info = self.provider(default_provider)
        return ModelRef(provider_id=provider_info.id, model_id=value, raw=model)

    def resolve_options(
        self,
        model_ref: ModelRef,
        *,
        provider_options: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Resolve API client options from env + provider defaults + overrides."""
        info = self.provider(model_ref.provider_id)
        options: dict[str, object] = {}

        api_key = os.getenv(info.api_key_env)
        if api_key:
            options["api_key"] = api_key

        if info.base_url:
            options["base_url"] = info.base_url

        if provider_options:
            options.update(provider_options)
        return options
