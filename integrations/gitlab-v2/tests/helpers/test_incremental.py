from datetime import datetime, timezone

import pytest

from gitlab.helpers.incremental import (
    GITLAB_INCREMENTAL,
    TAG_INCREMENTAL,
    GitlabQueryParams,
    build_merge_request_params,
    ensure_tag_created_at,
    with_incremental_cursor,
    with_project_incremental_cursor,
)

CURSOR = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
CURSOR_ISO = "2026-06-01T12:00:00Z"
LOOKBACK = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def cursor() -> datetime:
    return CURSOR


class TestGitLabIncrementalStrategy:
    def test_build_params_with_cursor(self, cursor: datetime) -> None:
        assert GITLAB_INCREMENTAL.build_params(cursor) == {
            "updated_after": CURSOR_ISO,
        }

    def test_build_params_without_cursor_returns_empty(self) -> None:
        assert GITLAB_INCREMENTAL.build_params(None) == {}

    def test_merge_params_preserves_base_keys(self, cursor: datetime) -> None:
        base: GitlabQueryParams = {"state": "opened", "labels": "bug"}
        assert with_incremental_cursor(base, cursor) == {
            "state": "opened",
            "labels": "bug",
            "updated_after": CURSOR_ISO,
        }

    def test_merge_params_without_cursor_is_noop(self) -> None:
        base: GitlabQueryParams = {"state": "closed", "non_archived": True}
        assert with_incremental_cursor(base, None) == base

    def test_cursor_overwrites_existing_updated_after(self, cursor: datetime) -> None:
        base: GitlabQueryParams = {"updated_after": "2025-01-01T00:00:00Z"}
        result = with_incremental_cursor(base, cursor)
        assert result["updated_after"] == CURSOR_ISO


class TestProjectIncrementalParams:
    def test_adds_updated_after_and_order_by(self, cursor: datetime) -> None:
        result = with_project_incremental_cursor(
            {"min_access_level": 30},
            cursor,
            has_search_queries=False,
        )
        assert result == {
            "min_access_level": 30,
            "updated_after": CURSOR_ISO,
            "order_by": "updated_at",
        }

    def test_skips_when_search_queries_present(self, cursor: datetime) -> None:
        base: GitlabQueryParams = {"min_access_level": 30}
        result = with_project_incremental_cursor(
            base,
            cursor,
            has_search_queries=True,
        )
        assert result == base

    def test_noop_without_cursor(self) -> None:
        base: GitlabQueryParams = {"active": True}
        assert (
            with_project_incremental_cursor(base, None, has_search_queries=False)
            == base
        )


class TestMergeRequestParams:
    def test_cursor_applies_to_opened(self, cursor: datetime) -> None:
        assert build_merge_request_params("opened", cursor, LOOKBACK) == {
            "state": "opened",
            "updated_after": CURSOR_ISO,
        }

    def test_cursor_applies_to_merged(self, cursor: datetime) -> None:
        assert build_merge_request_params("merged", cursor, LOOKBACK) == {
            "state": "merged",
            "updated_after": CURSOR_ISO,
        }

    def test_full_resync_skips_lookback_for_opened(self) -> None:
        assert build_merge_request_params("opened", None, LOOKBACK) == {
            "state": "opened",
        }

    def test_full_resync_applies_lookback_for_closed(self) -> None:
        assert build_merge_request_params("closed", None, LOOKBACK) == {
            "state": "closed",
            "updated_after": LOOKBACK,
        }


class TestTagIncremental:
    """T2 client-side cutoff for tags (newest-first, stop on ``created_at``)."""

    def test_build_params_is_empty(self, cursor: datetime) -> None:
        """No extra query params — API already returns newest-first."""
        assert TAG_INCREMENTAL.build_params(cursor) == {}

    def test_filter_page_keeps_only_newer_tags(self, cursor: datetime) -> None:
        page = [
            {"name": "v2", "created_at": "2026-06-02T00:00:00Z"},
            {"name": "v1", "created_at": "2026-05-01T00:00:00Z"},
        ]
        assert [t["name"] for t in TAG_INCREMENTAL.filter_page(page, cursor)] == ["v2"]

    def test_should_break_when_page_contains_older_tag(self, cursor: datetime) -> None:
        page = [
            {"name": "v2", "created_at": "2026-06-02T00:00:00Z"},
            {"name": "v1", "created_at": "2026-05-01T00:00:00Z"},
        ]
        assert TAG_INCREMENTAL.should_break_pagination(page, cursor) is True

    def test_should_not_break_when_all_newer(self, cursor: datetime) -> None:
        page = [
            {"name": "v3", "created_at": "2026-07-01T00:00:00Z"},
            {"name": "v2", "created_at": "2026-06-15T00:00:00Z"},
        ]
        assert TAG_INCREMENTAL.should_break_pagination(page, cursor) is False


class TestEnsureTagCreatedAt:
    """Backfill ``created_at`` for lightweight tags."""

    def test_keeps_existing_created_at(self) -> None:
        tag = {"name": "v1", "created_at": "2026-06-01T00:00:00Z"}
        assert ensure_tag_created_at(tag) is tag

    def test_falls_back_to_commit_date(self) -> None:
        tag = {
            "name": "v1",
            "created_at": None,
            "commit": {"committed_date": "2026-05-15T10:00:00Z"},
        }
        result = ensure_tag_created_at(tag)
        assert result["created_at"] == "2026-05-15T10:00:00Z"
        assert result is not tag  # returns a copy

    def test_noop_when_no_dates_available(self) -> None:
        tag = {"name": "v1"}
        assert ensure_tag_created_at(tag) is tag

    def test_noop_when_commit_has_no_date(self) -> None:
        tag = {"name": "v1", "created_at": None, "commit": {}}
        assert ensure_tag_created_at(tag) is tag
