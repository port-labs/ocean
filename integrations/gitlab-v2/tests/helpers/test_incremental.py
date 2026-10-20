from datetime import datetime, timezone

from gitlab.clients.options import IssueOptions
from gitlab.helpers.incremental import (
    build_deployment_params,
    build_issue_params,
    build_merge_request_params,
    build_pipeline_params,
    resolve_effective_datetime,
)

CURSOR = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
SELECTOR_UPDATED_AFTER = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)


def _options() -> IssueOptions:
    return IssueOptions(
        issue_type="issue",
        labels=None,
        non_archived=True,
        state="opened",
    )


def test_resolve_effective_datetime_prefers_cursor() -> None:
    assert resolve_effective_datetime(CURSOR, SELECTOR_UPDATED_AFTER) == CURSOR


def test_resolve_effective_datetime_falls_back_to_selector() -> None:
    assert (
        resolve_effective_datetime(None, SELECTOR_UPDATED_AFTER)
        == SELECTOR_UPDATED_AFTER
    )


def test_resolve_effective_datetime_none_when_both_missing() -> None:
    assert resolve_effective_datetime(None, None) is None


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
    """Time window must come from resolve_effective_datetime, not options."""
    options = IssueOptions(
        issue_type="issue",
        non_archived=True,
        state="opened",
        updated_after="2020-01-01T00:00:00+00:00",
    )
    params = build_issue_params(options, updated_after=CURSOR)

    assert params["updated_after"] == CURSOR.isoformat()


def test_mr_full_resync_opened_has_no_time_filter() -> None:
    params = build_merge_request_params(
        "opened", cursor=None, lookback_updated_after=SELECTOR_UPDATED_AFTER
    )

    assert params == {"state": "opened"}


def test_mr_full_resync_closed_uses_lookback() -> None:
    params = build_merge_request_params(
        "closed", cursor=None, lookback_updated_after=SELECTOR_UPDATED_AFTER
    )

    assert params == {
        "state": "closed",
        "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
    }


def test_mr_incremental_applies_cursor_to_opened() -> None:
    params = build_merge_request_params(
        "opened", cursor=CURSOR, lookback_updated_after=SELECTOR_UPDATED_AFTER
    )

    assert params == {"state": "opened", "updated_after": CURSOR.isoformat()}


def test_mr_incremental_applies_cursor_to_merged_over_lookback() -> None:
    params = build_merge_request_params(
        "merged", cursor=CURSOR, lookback_updated_after=SELECTOR_UPDATED_AFTER
    )

    assert params == {"state": "merged", "updated_after": CURSOR.isoformat()}


def test_pipeline_full_resync_keeps_selector_filters() -> None:
    params = build_pipeline_params(
        {
            "status": "success",
            "ref": "main",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
        },
        cursor=None,
    )

    assert params == {
        "status": "success",
        "ref": "main",
        "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
    }


def test_pipeline_full_resync_without_time_filter() -> None:
    assert build_pipeline_params({"status": "failed"}, cursor=None) == {
        "status": "failed"
    }


def test_pipeline_incremental_overrides_selector_updated_after() -> None:
    params = build_pipeline_params(
        {
            "scope": "finished",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
        },
        cursor=CURSOR,
    )

    assert params == {
        "scope": "finished",
        "updated_after": CURSOR.isoformat(),
    }


def test_pipeline_incremental_sets_updated_after_when_selector_has_none() -> None:
    params = build_pipeline_params({"status": "running"}, cursor=CURSOR)

    assert params == {
        "status": "running",
        "updated_after": CURSOR.isoformat(),
    }


def test_deployment_full_resync_keeps_selector_filters() -> None:
    params = build_deployment_params(
        {
            "environment": "production",
            "status": "success",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
            "order_by": "finished_at",
        },
        cursor=None,
    )

    assert params == {
        "environment": "production",
        "status": "success",
        "order_by": "updated_at",
        "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
    }


def test_deployment_incremental_overrides_selector_updated_after() -> None:
    params = build_deployment_params(
        {
            "environment": "staging",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
        },
        cursor=CURSOR,
    )

    assert params == {
        "environment": "staging",
        "updated_after": CURSOR.isoformat(),
        "order_by": "updated_at",
    }


def test_deployment_without_updated_after_keeps_finished_at_order() -> None:
    params = build_deployment_params(
        {"status": "success", "order_by": "finished_at"},
        cursor=None,
    )

    assert params == {"status": "success", "order_by": "finished_at"}


def test_deployment_incremental_with_finished_window_skips_cursor() -> None:
    params = build_deployment_params(
        {
            "status": "success",
            "finished_after": "2024-01-01T00:00:00Z",
            "finished_before": "2024-06-01T00:00:00Z",
            "order_by": "finished_at",
        },
        cursor=CURSOR,
    )

    assert params == {
        "status": "success",
        "finished_after": "2024-01-01T00:00:00Z",
        "finished_before": "2024-06-01T00:00:00Z",
        "order_by": "finished_at",
    }


def test_deployment_finished_window_drops_selector_updated_after() -> None:
    params = build_deployment_params(
        {
            "status": "success",
            "finished_after": "2024-01-01T00:00:00Z",
            "updated_after": SELECTOR_UPDATED_AFTER.isoformat(),
        },
        cursor=None,
    )

    assert params == {
        "status": "success",
        "finished_after": "2024-01-01T00:00:00Z",
        "order_by": "finished_at",
    }
