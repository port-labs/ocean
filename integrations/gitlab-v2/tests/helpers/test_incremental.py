from datetime import datetime, timezone

import pytest

from gitlab.clients.options import IssueOptions
from gitlab.clients.utils import (
    build_issue_params,
    build_merge_request_params,
    build_pipeline_params,
)
from gitlab.helpers.incremental import (
    build_cursor_updated_after_params,
    build_incremental_merge_request_params,
    build_incremental_pipeline_params,
    build_incremental_project_updated_params,
    build_incremental_projects_params,
)


@pytest.fixture
def no_visibility_params(monkeypatch):
    """Visibility config needs a Port event context; these tests don't use it."""
    monkeypatch.setattr("gitlab.clients.utils.build_visibility_params", lambda: {})


CURSOR = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
SELECTOR_UPDATED_AFTER = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)


def _options() -> IssueOptions:
    return IssueOptions(
        issue_type="issue",
        labels=None,
        non_archived=True,
        state="opened",
    )


# --- Projects -----------------------------------------------------------------


def test_incremental_projects_sets_last_activity_after(no_visibility_params) -> None:
    assert build_incremental_projects_params(True, CURSOR) == {
        "active": True,
        "last_activity_after": CURSOR.isoformat(),
    }


def test_incremental_project_updated_sets_updated_after_and_order(
    no_visibility_params,
) -> None:
    assert build_incremental_project_updated_params(True, CURSOR) == {
        "active": True,
        "updated_after": CURSOR.isoformat(),
        "order_by": "updated_at",
    }


def test_incremental_project_updated_without_active_filter(
    no_visibility_params,
) -> None:
    assert build_incremental_project_updated_params(None, CURSOR) == {
        "updated_after": CURSOR.isoformat(),
        "order_by": "updated_at",
    }


def test_cursor_params_keep_base_and_replace_selector_timestamps() -> None:
    params = build_cursor_updated_after_params(
        {
            "min_access_level": 30,
            "active": True,
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
            "updated_before": "2024-12-01T00:00:00Z",
            "order_by": "last_activity_at",
        },
        CURSOR,
    )

    assert params == {
        "min_access_level": 30,
        "active": True,
        "updated_after": CURSOR.isoformat(),
        "order_by": "updated_at",
    }


# --- Issues -------------------------------------------------------------------


def test_full_resync_keeps_selector_filters_and_drops_unset_ones() -> None:
    assert build_issue_params(_options(), updated_after=SELECTOR_UPDATED_AFTER) == {
        "issue_type": "issue",
        "non_archived": True,
        "state": "opened",
        "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
    }


def test_full_resync_without_selector_date_fetches_all_issues() -> None:
    assert "updated_after" not in build_issue_params(_options(), updated_after=None)


def test_incremental_cursor_sets_updated_after() -> None:
    params = build_issue_params(_options(), updated_after=CURSOR)

    assert params["updated_after"] == CURSOR.isoformat()
    # Other selector filters still apply on incremental runs.
    assert params["state"] == "opened"
    assert params["issue_type"] == "issue"


def test_build_issue_params_ignores_options_updated_after_field() -> None:
    """The time window comes from the updated_after argument, not from options."""
    options = IssueOptions(
        issue_type="issue",
        non_archived=True,
        state="opened",
        updated_after="2020-01-01T00:00:00+00:00",
    )
    params = build_issue_params(options, updated_after=CURSOR)

    assert params["updated_after"] == CURSOR.isoformat()


# --- Merge requests -----------------------------------------------------------


def test_mr_full_resync_opened_has_no_time_filter() -> None:
    assert build_merge_request_params("opened", SELECTOR_UPDATED_AFTER) == {
        "state": "opened"
    }


def test_mr_full_resync_closed_uses_lookback() -> None:
    assert build_merge_request_params("closed", SELECTOR_UPDATED_AFTER) == {
        "state": "closed",
        "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
    }


def test_mr_incremental_applies_cursor_to_opened() -> None:
    assert build_incremental_merge_request_params("opened", CURSOR) == {
        "state": "opened",
        "updated_after": CURSOR.isoformat(),
    }


def test_mr_incremental_applies_cursor_to_merged() -> None:
    assert build_incremental_merge_request_params("merged", CURSOR) == {
        "state": "merged",
        "updated_after": CURSOR.isoformat(),
    }


# --- Pipelines ----------------------------------------------------------------


def test_pipeline_full_resync_keeps_selector_filters() -> None:
    params = build_pipeline_params(
        {
            "status": "success",
            "ref": "main",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
        },
    )

    assert params == {
        "status": "success",
        "ref": "main",
        "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
    }


def test_pipeline_full_resync_without_time_filter() -> None:
    assert build_pipeline_params({"status": "failed"}) == {"status": "failed"}


def test_pipeline_incremental_overrides_selector_updated_after() -> None:
    params = build_incremental_pipeline_params(
        {
            "scope": "finished",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
        },
        CURSOR,
    )

    assert params == {
        "scope": "finished",
        "updated_after": CURSOR.isoformat(),
    }


def test_pipeline_incremental_sets_updated_after_when_selector_has_none() -> None:
    assert build_incremental_pipeline_params({"status": "running"}, CURSOR) == {
        "status": "running",
        "updated_after": CURSOR.isoformat(),
    }


# --- Deployments (cursor-updated params) --------------------------------------


def test_deployment_incremental_overrides_selector_updated_after() -> None:
    params = build_cursor_updated_after_params(
        {"updated_after": SELECTOR_UPDATED_AFTER.isoformat()},
        CURSOR,
    )

    assert params == {
        "updated_after": CURSOR.isoformat(),
        "order_by": "updated_at",
    }


def test_deployment_incremental_drops_finished_order_by() -> None:
    params = build_cursor_updated_after_params(
        {"status": "success", "order_by": "finished_at"},
        CURSOR,
    )

    assert params == {
        "status": "success",
        "updated_after": CURSOR.isoformat(),
        "order_by": "updated_at",
    }


def test_deployment_incremental_ignores_timestamp_selectors_and_keeps_filters() -> None:
    params = build_cursor_updated_after_params(
        {
            "environment": "production",
            "status": "success",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
            "updated_before": "2024-12-01T00:00:00Z",
            "finished_after": "2024-01-01T00:00:00Z",
            "finished_before": "2024-06-01T00:00:00Z",
            "order_by": "finished_at",
        },
        CURSOR,
    )

    assert params == {
        "environment": "production",
        "status": "success",
        "updated_after": CURSOR.isoformat(),
        "order_by": "updated_at",
    }


def test_pipeline_incremental_raises_on_malformed_selector_updated_after() -> None:
    with pytest.raises(ValueError):
        build_incremental_pipeline_params({"updated_after": "not-a-date"}, CURSOR)
