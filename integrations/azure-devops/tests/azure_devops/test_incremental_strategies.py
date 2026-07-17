from datetime import datetime, timezone

import pytest

from azure_devops.incremental import (
    BUILD_INCREMENTAL,
    RELEASE_DEPLOYMENT_INCREMENTAL,
    RELEASE_INCREMENTAL,
    build_pipeline_runs_analytics_filter,
    flatten_advanced_security_params,
    merge_advanced_security_incremental,
    wiql_changed_after_clause,
)

CURSOR = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "strategy,expected_key,expected_value",
    [
        (BUILD_INCREMENTAL, "minTime", CURSOR.isoformat()),
        (RELEASE_INCREMENTAL, "minCreatedTime", CURSOR.isoformat()),
        (RELEASE_DEPLOYMENT_INCREMENTAL, "minModifiedTime", CURSOR.isoformat()),
    ],
)
def test_build_params_with_cursor(
    strategy: object, expected_key: str, expected_value: str
) -> None:
    assert strategy.build_params(CURSOR) == {expected_key: expected_value}  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "strategy",
    [BUILD_INCREMENTAL, RELEASE_INCREMENTAL, RELEASE_DEPLOYMENT_INCREMENTAL],
)
def test_build_params_without_cursor_returns_empty(strategy: object) -> None:
    assert strategy.build_params(None) == {}  # type: ignore[attr-defined]


def test_build_merge_params_overrides_selector_min_created_time() -> None:
    assert RELEASE_INCREMENTAL.merge_params(
        {"minCreatedTime": "2020-01-01"}, CURSOR
    ) == {"minCreatedTime": CURSOR.isoformat()}


def test_merge_advanced_security_incremental_adds_modified_since() -> None:
    assert merge_advanced_security_incremental(
        {"criteria": {"states": "active"}}, CURSOR
    ) == {
        "criteria": {
            "states": "active",
            "modifiedSince": CURSOR.isoformat(),
        }
    }


def test_merge_advanced_security_incremental_noop_without_cursor() -> None:
    params = {"criteria": {"states": "active"}}
    assert merge_advanced_security_incremental(params, None) is params


def test_wiql_changed_after_clause_uses_date_precision_only() -> None:
    assert (
        wiql_changed_after_clause(CURSOR)
        == "[System.ChangedDate] >= '2026-06-01'"
    )


def test_flatten_advanced_security_params_expands_criteria() -> None:
    assert flatten_advanced_security_params(
        {
            "api-version": "7.2-preview.1",
            "criteria": {
                "states": "active",
                "modifiedSince": CURSOR.isoformat(),
            },
        }
    ) == {
        "api-version": "7.2-preview.1",
        "criteria.states": "active",
        "criteria.modifiedSince": CURSOR.isoformat(),
    }


def test_build_pipeline_runs_analytics_filter_cursor_only() -> None:
    assert (
        build_pipeline_runs_analytics_filter(CURSOR)
        == f"CompletedDate ge {CURSOR.isoformat()}"
    )
