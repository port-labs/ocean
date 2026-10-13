import pytest

from jira.actions.utils import (
    get_issue_browse_url,
    plain_text_adf,
)


def test_plain_text_adf() -> None:
    adf = plain_text_adf("Hello world")
    assert adf["type"] == "doc"
    assert adf["content"][0]["content"][0]["text"] == "Hello world"


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
