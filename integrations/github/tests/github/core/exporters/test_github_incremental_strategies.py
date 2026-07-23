from datetime import datetime, timezone

import pytest

from github.core.exporters.code_scanning_alert_exporter import CODE_SCANNING_INCREMENTAL
from github.core.exporters.dependabot_exporter import DEPENDABOT_INCREMENTAL
from github.core.exporters.deployment_exporter import DEPLOYMENT_INCREMENTAL
from github.core.exporters.issue_exporter import ISSUE_INCREMENTAL
from github.core.exporters.pull_request_exporter.core import (
    OPEN_PULL_REQUEST_INCREMENTAL_GRAPHQL,
    OPEN_PULL_REQUEST_INCREMENTAL_REST,
)
from github.core.exporters.release_exporter import RELEASE_INCREMENTAL
from github.core.exporters.repository_exporter import REPOSITORY_INCREMENTAL
from github.core.exporters.workflow_runs_exporter import WORKFLOW_RUN_INCREMENTAL


@pytest.fixture
def cursor() -> datetime:
    return datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        (
            ISSUE_INCREMENTAL,
            {"since": "2026-06-01T12:00:00+00:00"},
        ),
        (
            WORKFLOW_RUN_INCREMENTAL,
            {"created": ">=2026-06-01T12:00:00Z"},
        ),
        (
            RELEASE_INCREMENTAL,
            {},
        ),
        (
            DEPLOYMENT_INCREMENTAL,
            {},
        ),
        (
            DEPENDABOT_INCREMENTAL,
            {"sort": "updated", "direction": "desc"},
        ),
        (
            CODE_SCANNING_INCREMENTAL,
            {"sort": "updated", "direction": "desc"},
        ),
        (
            REPOSITORY_INCREMENTAL,
            {"sort": "created", "direction": "desc"},
        ),
        (
            OPEN_PULL_REQUEST_INCREMENTAL_REST,
            {"sort": "updated", "direction": "desc"},
        ),
        (
            OPEN_PULL_REQUEST_INCREMENTAL_GRAPHQL,
            {},
        ),
    ],
)
def test_build_params_with_cursor(
    strategy: object,
    expected: dict[str, str],
    cursor: datetime,
) -> None:
    assert strategy.build_params(cursor) == expected  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "strategy",
    [
        ISSUE_INCREMENTAL,
        WORKFLOW_RUN_INCREMENTAL,
        RELEASE_INCREMENTAL,
        DEPLOYMENT_INCREMENTAL,
        DEPENDABOT_INCREMENTAL,
        CODE_SCANNING_INCREMENTAL,
        REPOSITORY_INCREMENTAL,
        OPEN_PULL_REQUEST_INCREMENTAL_REST,
        OPEN_PULL_REQUEST_INCREMENTAL_GRAPHQL,
    ],
)
def test_build_params_without_cursor_returns_empty(strategy: object) -> None:
    assert strategy.build_params(None) == {}  # type: ignore[attr-defined]


def test_issue_merge_params_spreads_into_base(cursor: datetime) -> None:
    assert ISSUE_INCREMENTAL.merge_params({"state": "all"}, cursor) == {
        "state": "all",
        "since": "2026-06-01T12:00:00+00:00",
    }
