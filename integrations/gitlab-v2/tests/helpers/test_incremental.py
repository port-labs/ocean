from datetime import datetime, timezone

import pytest

from gitlab.helpers.incremental import (
    GITLAB_INCREMENTAL,
    GitlabQueryParams,
    build_merge_request_params,
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
