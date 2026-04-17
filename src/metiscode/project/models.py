"""Project models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProjectTime(BaseModel):
    """Project timestamps."""

    model_config = ConfigDict(extra="forbid")
    created: int
    updated: int
    initialized: int | None = None


class ProjectInfo(BaseModel):
    """Persisted project metadata."""

    model_config = ConfigDict(extra="forbid")
    id: str
    worktree: str
    vcs: Literal["git"] | None = None
    sandboxes: list[str]
    time: ProjectTime


class ProjectResolution(BaseModel):
    """Resolution output from a directory probe."""

    model_config = ConfigDict(extra="forbid")
    project: ProjectInfo
    sandbox: str

