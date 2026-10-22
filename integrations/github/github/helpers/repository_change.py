from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from github.helpers.utils import parse_timestamp


class RepositoryChangeField(StrEnum):
    """Repository timestamp that marks the changes a kind cares about."""

    # Repository metadata (settings, description, topics); used by the repository kind.
    UPDATED = "updated_at"
    # Any git push (branch or tag); used by content kinds (file, folder, tag, workflow, ...).
    PUSHED = "pushed_at"


@dataclass(frozen=True)
class RepositoryChange:
    """Incremental repository filter: repositories whose ``field`` is at or after ``since``."""

    since: datetime
    field: RepositoryChangeField

    @classmethod
    def updated(cls, since: datetime | None) -> RepositoryChange | None:
        return cls(since, RepositoryChangeField.UPDATED) if since else None

    @classmethod
    def pushed(cls, since: datetime | None) -> RepositoryChange | None:
        return cls(since, RepositoryChangeField.PUSHED) if since else None

    def matches(self, repo: dict[str, Any]) -> bool:
        """Whether ``repo`` changed since the cursor; a missing timestamp counts as changed."""
        raw = repo.get(self.field.value)
        changed_at = parse_timestamp(raw) if raw else None
        return changed_at is None or changed_at >= self.since
