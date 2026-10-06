"""Data models for Ocean auto-version CI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseTarget:
    kind: str  # "integration" | "core"
    name: str
    pyproject_path: Path
    changelog_path: Path

    @property
    def label(self) -> str:
        return self.name if self.kind == "integration" else "ocean-core"

    @property
    def work_dir(self) -> Path:
        return self.pyproject_path.parent

    @property
    def release_hint(self) -> str:
        if self.kind == "integration":
            return f"integrations/{self.name}/.ocean-release/<name>.yaml"
        return ".ocean-release/core/<name>.yaml"


@dataclass(frozen=True)
class ReleaseIntent:
    path: Path
    bump: str
    changelog_type: str
    changelog: str


@dataclass(frozen=True)
class ParsedVersion:
    major: int
    minor: int
    patch: int
    suffix: str = ""

    def format(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}{self.suffix}"


@dataclass
class AppliedRelease:
    target: ReleaseTarget
    previous_version: str
    new_version: str
    bump: str
    changelog: str
    release_file: str
    integration_type: str
    context_dir: str

    def to_dict(self) -> dict[str, str]:
        return {
            "target": self.target.label,
            "kind": self.target.kind,
            "name": self.target.name,
            "integration_type": self.integration_type,
            "previous_version": self.previous_version,
            "new_version": self.new_version,
            "bump": self.bump,
            "changelog": self.changelog,
            "release_file": self.release_file,
            "context_dir": self.context_dir,
        }
