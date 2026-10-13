from typing import Any


def plain_text_adf(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def get_issue_browse_url(
    jira_url: str, issue_key: str, *, oauth_enabled: bool = False
) -> str | None:
    if oauth_enabled:
        return None
    return f"{jira_url.rstrip('/')}/browse/{issue_key}"
