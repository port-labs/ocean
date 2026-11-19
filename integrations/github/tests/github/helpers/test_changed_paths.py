from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from github.helpers.changed_paths import (
    COMMIT_COMPARE_MAX_FILES,
    GIT_NULL_SHA,
    ancestor_dirs,
    changed_paths_since,
)

SINCE = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
# Skip the per-event cache so each test sees its own responses.
_changed_paths_since = changed_paths_since.__wrapped__  # type: ignore[attr-defined]


def _activity(timestamp: str, after: str = "a" * 40) -> dict[str, Any]:
    return {"timestamp": timestamp, "before": "0" * 39 + "1", "after": after}


def _compare_url(client: MagicMock) -> str:
    return client.send_api_request.call_args.args[0]


def _client(
    activity_pages: list[list[dict[str, Any]]], compare: dict[str, Any] | None = None
) -> MagicMock:
    async def _pages(*args: Any, **kwargs: Any) -> AsyncIterator[list[dict[str, Any]]]:
        for page in activity_pages:
            yield page

    client = MagicMock()
    client.base_url = "https://api.github.com"
    client.send_paginated_request = MagicMock(side_effect=_pages)
    client.send_api_request = AsyncMock(return_value=compare or {})
    return client


async def _changed(client: MagicMock) -> list[str] | None:
    return await _changed_paths_since(client, "org", "repo", "main", SINCE)


@pytest.mark.asyncio
class TestChangedPathsSince:
    async def test_without_since_changes_are_unknown(self) -> None:
        client = _client([])

        assert await _changed_paths_since(client, "org", "repo", "main", None) is None
        client.send_paginated_request.assert_not_called()

    async def test_compares_from_the_branch_tip_at_since(self) -> None:
        client = _client(
            [
                [_activity("2026-06-03T00:00:00Z", after="b" * 40)],
                [
                    _activity("2026-06-02T00:00:00Z", after="c" * 40),
                    _activity("2026-05-30T00:00:00Z", after="d" * 40),
                    _activity("2026-05-29T00:00:00Z", after="e" * 40),
                ],
            ],
            compare={
                "status": "ahead",
                "files": [
                    {"filename": "a/port.yml", "status": "modified"},
                    {"filename": "b/new.yml", "status": "added"},
                    {"filename": "c/old.yml", "status": "removed"},
                ],
            },
        )

        assert await _changed(client) == ["a/port.yml", "b/new.yml"]
        assert _compare_url(client).endswith(
            f"/repos/org/repo/compare/{'d' * 40}...main"
        )

    async def test_push_missing_from_activity_is_still_compared(self) -> None:
        """The activity can lag behind a push; the compare to the live tip still sees it."""
        client = _client(
            [[_activity("2026-05-30T00:00:00Z", after="d" * 40)]],
            compare={
                "status": "ahead",
                "files": [{"filename": "new/README.md", "status": "added"}],
            },
        )

        assert await _changed(client) == ["new/README.md"]
        assert _compare_url(client).endswith(f"/compare/{'d' * 40}...main")

    async def test_identical_compare_means_nothing_changed(self) -> None:
        client = _client(
            [[_activity("2026-05-30T00:00:00Z")]],
            compare={"status": "identical", "files": []},
        )

        assert await _changed(client) == []

    @pytest.mark.parametrize(
        "pages",
        [
            [],
            [[_activity("2026-06-02T00:00:00Z")]],
        ],
        ids=["no-activity", "activity-ends-after-since"],
    )
    async def test_activity_not_reaching_since_needs_full_listing(
        self, pages: list[list[dict[str, Any]]]
    ) -> None:
        assert await _changed(_client(pages)) is None

    async def test_branch_missing_at_since_needs_full_listing(self) -> None:
        client = _client(
            [
                [
                    _activity("2026-06-02T00:00:00Z"),
                    _activity("2026-05-30T00:00:00Z", after=GIT_NULL_SHA),
                ]
            ]
        )

        assert await _changed(client) is None
        client.send_api_request.assert_not_called()

    @pytest.mark.parametrize(
        "compare",
        [
            {},
            {"status": "diverged", "files": []},
            {
                "status": "ahead",
                "files": [
                    {"filename": f"f{i}", "status": "modified"}
                    for i in range(COMMIT_COMPARE_MAX_FILES)
                ],
            },
        ],
        ids=["unreadable", "rewritten-history", "may-be-cut-off"],
    )
    async def test_untrusted_compare_needs_full_listing(
        self, compare: dict[str, Any]
    ) -> None:
        client = _client(
            [[_activity("2026-06-02T00:00:00Z"), _activity("2026-05-30T00:00:00Z")]],
            compare=compare,
        )

        assert await _changed(client) is None

    async def test_api_error_needs_full_listing(self) -> None:
        client = _client(
            [[_activity("2026-06-02T00:00:00Z"), _activity("2026-05-30T00:00:00Z")]]
        )
        client.send_api_request.side_effect = httpx.ConnectError("boom")

        assert await _changed(client) is None


def test_ancestor_dirs() -> None:
    assert ancestor_dirs(["a/b/c.txt", "root.txt", "a/d.txt"]) == {"a", "a/b"}
