from datetime import datetime, timezone

import pytest

from github.helpers.repository_change import RepositoryChange, RepositoryChangeField

CURSOR = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_constructors_return_none_without_cursor() -> None:
    assert RepositoryChange.updated(None) is None
    assert RepositoryChange.pushed(None) is None


def test_constructors_set_field() -> None:
    assert RepositoryChange.updated(CURSOR) == RepositoryChange(
        CURSOR, RepositoryChangeField.UPDATED
    )
    assert RepositoryChange.pushed(CURSOR) == RepositoryChange(
        CURSOR, RepositoryChangeField.PUSHED
    )


@pytest.mark.parametrize(
    ("change", "repo", "expected"),
    [
        # pushed_at drives content kinds, regardless of updated_at.
        (
            RepositoryChange.pushed(CURSOR),
            {"pushed_at": "2026-10-02T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"},
            True,
        ),
        (
            RepositoryChange.pushed(CURSOR),
            {"pushed_at": "2026-09-01T00:00:00Z", "updated_at": "2026-10-05T00:00:00Z"},
            False,
        ),
        # updated_at drives the repository kind, regardless of pushed_at.
        (
            RepositoryChange.updated(CURSOR),
            {"pushed_at": "2026-10-02T00:00:00Z", "updated_at": "2026-09-01T00:00:00Z"},
            False,
        ),
        (
            RepositoryChange.updated(CURSOR),
            {"updated_at": "2026-10-01T00:00:00Z"},
            True,
        ),
        # Unknown timestamp is treated as changed so nothing is silently skipped.
        (RepositoryChange.pushed(CURSOR), {}, True),
    ],
    ids=[
        "pushed-after",
        "pushed-before",
        "updated-before",
        "updated-at-cursor",
        "missing-timestamp",
    ],
)
def test_matches(
    change: RepositoryChange, repo: dict[str, str], expected: bool
) -> None:
    assert change.matches(repo) is expected
