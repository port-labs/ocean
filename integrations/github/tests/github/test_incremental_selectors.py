from datetime import datetime, timezone

from integration import (
    GithubCodeScanningAlertSelector,
    GithubDeploymentSelector,
    GithubDependabotAlertSelector,
    GithubIssueSelector,
    GithubReleaseSelector,
    GithubRepositorySelector,
)

CURSOR_ISO = "2026-06-01T12:00:00Z"
DATE_ONLY = "2026-01-01"


def test_repository_selector_updated_since_datetime() -> None:
    selector = GithubRepositorySelector(query="true", updatedSince=CURSOR_ISO)
    assert selector.updated_since_datetime == datetime(
        2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
    )


def test_issue_selector_updated_since_datetime() -> None:
    selector = GithubIssueSelector(query="true", updatedSince=CURSOR_ISO)
    assert selector.updated_since_datetime == datetime(
        2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
    )


def test_issue_selector_date_only_uses_utc_midnight() -> None:
    selector = GithubIssueSelector(query="true", updatedSince=DATE_ONLY)
    assert selector.updated_since_datetime == datetime(
        2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc
    )


def test_release_selector_created_since_datetime() -> None:
    selector = GithubReleaseSelector(query="true", createdSince=CURSOR_ISO)
    assert selector.created_since_datetime == datetime(
        2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
    )


def test_deployment_selector_created_since_datetime() -> None:
    selector = GithubDeploymentSelector(query="true", createdSince=CURSOR_ISO)
    assert selector.created_since_datetime == datetime(
        2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
    )


def test_dependabot_selector_updated_since_datetime() -> None:
    selector = GithubDependabotAlertSelector(query="true", updatedSince=CURSOR_ISO)
    assert selector.updated_since_datetime == datetime(
        2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
    )


def test_code_scanning_selector_updated_since_datetime() -> None:
    selector = GithubCodeScanningAlertSelector(query="true", updatedSince=CURSOR_ISO)
    assert selector.updated_since_datetime == datetime(
        2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
    )
