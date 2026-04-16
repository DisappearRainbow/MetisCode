"""Config schemas for metiscode."""

from pydantic import BaseModel, ConfigDict, Field


class AgentConfig(BaseModel):
    """Per-agent config placeholder."""

    model_config = ConfigDict(extra="forbid")
    model: str | None = None


class ProviderConfig(BaseModel):
    """Provider configuration."""

    model_config = ConfigDict(extra="forbid")
    npm: str | None = None
    options: dict[str, object] | None = None


class ConfigInfo(BaseModel):
    """Top-level configuration object."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_url: str | None = Field(default=None, alias="$schema")
    model: str | None = None
    small_model: str | None = None
    username: str | None = None
    instructions: list[str] | None = None
    plugin: list[str] | None = None
    tools: dict[str, bool] | None = None
    provider: dict[str, ProviderConfig] | None = None
    permission: dict[str, str] | None = None
    agent: dict[str, AgentConfig] | None = None
    mode: dict[str, AgentConfig] | None = None

