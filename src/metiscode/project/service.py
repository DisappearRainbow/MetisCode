"""Project discovery service."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

from metiscode.project.models import ProjectInfo, ProjectResolution, ProjectTime

log = structlog.get_logger(__name__)

GLOBAL_PROJECT_ID = "global"


@dataclass(slots=True, frozen=True)
class _GitResult:
    code: int
    stdout: str
    stderr: str


def _resolve_git_path(cwd: Path, value: str) -> Path:
    clean_value = value.rstrip("\r\n").strip()
    if not clean_value:
        return cwd
    git_path = Path(clean_value)
    if git_path.is_absolute():
        return git_path.resolve()
    return (cwd / git_path).resolve()


def _contains(base: Path, target: Path) -> bool:
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    try:
        common = os.path.commonpath([str(base_resolved), str(target_resolved)])
    except ValueError:
        return False
    return common == str(base_resolved)


def contains_path(*, directory: str, worktree: str, filepath: str) -> bool:
    """Check whether a file path is within project boundary."""
    file_path = Path(filepath)
    if _contains(Path(directory), file_path):
        return True
    if worktree == "/":
        return False
    return _contains(Path(worktree), file_path)


class ProjectService:
    """Directory-to-project resolver."""

    async def from_directory(self, directory: str) -> ProjectResolution:
        resolved_directory = Path(directory).resolve()
        discovery = await self._discover(resolved_directory)
        now = int(time.time() * 1000)

        project = ProjectInfo(
            id=discovery.id,
            worktree=discovery.worktree,
            vcs=discovery.vcs,
            sandboxes=[],
            time=ProjectTime(created=now, updated=now),
        )
        if discovery.sandbox != discovery.worktree and discovery.sandbox not in project.sandboxes:
            project.sandboxes.append(discovery.sandbox)

        return ProjectResolution(project=project, sandbox=discovery.sandbox)

    @dataclass(slots=True, frozen=True)
    class _Discovery:
        id: str
        worktree: str
        sandbox: str
        vcs: Literal["git"] | None

    async def _discover(self, directory: Path) -> _Discovery:
        dot_git = self._find_dot_git(directory)
        if dot_git is None:
            return self._Discovery(
                id=GLOBAL_PROJECT_ID,
                worktree="/",
                sandbox="/",
                vcs=None,
            )

        sandbox = dot_git.parent.resolve()
        project_id = self._read_cached_project_id(dot_git)
        git_binary = shutil.which("git")
        if git_binary is None:
            fallback_id = project_id or GLOBAL_PROJECT_ID
            sandbox_str = str(sandbox)
            return self._Discovery(
                id=fallback_id,
                worktree=sandbox_str,
                sandbox=sandbox_str,
                vcs=None,
            )

        common_dir = await self._run_git(["rev-parse", "--git-common-dir"], cwd=sandbox)
        if common_dir.code != 0:
            fallback_id = project_id or GLOBAL_PROJECT_ID
            sandbox_str = str(sandbox)
            return self._Discovery(
                id=fallback_id,
                worktree=sandbox_str,
                sandbox=sandbox_str,
                vcs=None,
            )

        common_path = _resolve_git_path(sandbox, common_dir.stdout)
        worktree = common_path if common_path == sandbox else common_path.parent

        if project_id is None:
            project_id = self._read_cached_project_id(worktree / ".git")

        if project_id is None:
            rev_list = await self._run_git(["rev-list", "--max-parents=0", "HEAD"], cwd=sandbox)
            roots = sorted(line.strip() for line in rev_list.stdout.splitlines() if line.strip())
            project_id = roots[0] if roots else None
            if project_id is not None:
                self._write_cached_project_id(worktree / ".git", project_id)

        if project_id is None:
            return self._Discovery(
                id=GLOBAL_PROJECT_ID,
                worktree=str(sandbox),
                sandbox=str(sandbox),
                vcs="git",
            )

        top_level = await self._run_git(["rev-parse", "--show-toplevel"], cwd=sandbox)
        if top_level.code != 0:
            sandbox_str = str(sandbox)
            return self._Discovery(
                id=project_id,
                worktree=sandbox_str,
                sandbox=sandbox_str,
                vcs=None,
            )

        sandbox = _resolve_git_path(sandbox, top_level.stdout)
        return self._Discovery(
            id=project_id,
            worktree=str(worktree),
            sandbox=str(sandbox),
            vcs="git",
        )

    def _find_dot_git(self, start: Path) -> Path | None:
        current = start
        while True:
            candidate = current / ".git"
            if candidate.exists():
                return candidate
            if current.parent == current:
                return None
            current = current.parent

    async def _run_git(self, args: list[str], cwd: Path) -> _GitResult:
        def _run() -> _GitResult:
            completed = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                shell=False,
                check=False,
            )
            return _GitResult(
                code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )

        return await asyncio.to_thread(_run)

    def _read_cached_project_id(self, git_dir: Path) -> str | None:
        marker = git_dir / "opencode"
        if not marker.exists():
            return None
        value = marker.read_text(encoding="utf-8").strip()
        return value if value else None

    def _write_cached_project_id(self, git_dir: Path, project_id: str) -> None:
        marker = git_dir / "opencode"
        try:
            marker.write_text(project_id, encoding="utf-8")
        except OSError:
            log.debug("failed to write cached project id", path=str(marker))
