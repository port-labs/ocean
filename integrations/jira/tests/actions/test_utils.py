import pytest

from jira.actions.utils import (
    build_create_issue_payload,
    get_issue_browse_url,
    plain_text_adf,
)


def test_plain_text_adf() -> None:
    adf = plain_text_adf("Hello world")
    assert adf["type"] == "doc"
    assert adf["content"][0]["content"][0]["text"] == "Hello world"


def test_build_create_issue_payload_required_fields_only() -> None:
    payload = build_create_issue_payload(
        project="PORT",
        issue_type="Task",
        summary="Summary",
    )
    assert payload == {
        "fields": {
            "project": {"key": "PORT"},
            "issuetype": {"name": "Task"},
            "summary": "Summary",
        }
    }


def test_build_create_issue_payload_with_optional_fields() -> None:
    payload = build_create_issue_payload(
        project="PORT",
        issue_type="Bug",
        summary="Summary",
        description="Details",
        priority="High",
        assignee_account_id="abc-123",
    )
    assert payload["fields"]["description"] == plain_text_adf("Details")
    assert payload["fields"]["priority"] == {"name": "High"}
    assert payload["fields"]["assignee"] == {"id": "abc-123"}


@pytest.mark.parametrize(
    ("jira_url", "issue_key", "expected"),
    [
        (
            "https://example.atlassian.net",
            "PORT-1",
            "https://example.atlassian.net/browse/PORT-1",
        ),
        (
            "https://example.atlassian.net/",
            "PORT-2",
            "https://example.atlassian.net/browse/PORT-2",
        ),
    ],
)
def test_get_issue_browse_url_for_basic_auth(
    jira_url: str, issue_key: str, expected: str
) -> None:
    assert get_issue_browse_url(jira_url, issue_key) == expected


def test_get_issue_browse_url_returns_none_for_oauth() -> None:
    assert (
        get_issue_browse_url(
            "https://api.atlassian.com/ex/jira/cloud-id",
            "PORT-1",
            oauth_enabled=True,
        )
        is None
    )
