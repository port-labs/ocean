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


def build_create_issue_payload(
    project: str,
    issue_type: str,
    summary: str,
    description: str | None = None,
    priority: str | None = None,
    assignee_account_id: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "project": {"key": project},
        "issuetype": {"name": issue_type},
        "summary": summary,
    }
    if description:
        fields["description"] = plain_text_adf(description)
    if priority:
        fields["priority"] = {"name": priority}
    if assignee_account_id:
        fields["assignee"] = {"id": assignee_account_id}
    return {"fields": fields}


def get_issue_browse_url(
    jira_url: str, issue_key: str, *, oauth_enabled: bool = False
) -> str | None:
    if oauth_enabled:
        return None
    return f"{jira_url.rstrip('/')}/browse/{issue_key}"
