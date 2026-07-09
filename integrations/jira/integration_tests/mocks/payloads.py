from typing import Any

# Basic auth path (non api.atlassian.com host) — no auth HTTP round-trip needed.
JIRA_HOST = "https://mycompany.atlassian.net"
JIRA_EMAIL = "test@mycompany.com"
JIRA_TOKEN = "test-api-token"

JIRA_REST_URL = f"{JIRA_HOST}/rest"
JIRA_API_URL = f"{JIRA_REST_URL}/api/3"

PROJECT_KEYS = ["PORT", "OCEAN"]
ISSUE_COUNT = 2
USER_COUNT = 2


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def project_response(key: str, idx: int) -> dict[str, Any]:
    return {
        "key": key,
        "id": str(10000 + idx),
        "name": f"Project {key}",
        "self": f"{JIRA_API_URL}/project/{10000 + idx}",
        "insight": {"totalIssueCount": idx * 10},
    }


def projects_page_response() -> dict[str, Any]:
    values = [project_response(k, i) for i, k in enumerate(PROJECT_KEYS, start=1)]
    return {
        "values": values,
        "total": len(values),
        "startAt": 0,
        "maxResults": 50,
    }


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

def issue_response(idx: int) -> dict[str, Any]:
    key = f"PORT-{idx}"
    return {
        "key": key,
        "id": str(20000 + idx),
        "self": f"{JIRA_API_URL}/issue/{key}",
        "fields": {
            "summary": f"Test issue {idx}",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
            "creator": {"emailAddress": f"creator{idx}@test.com"},
            "priority": {"name": "Medium"},
            "labels": [f"label-{idx}"],
            "components": [],
            "created": f"2024-01-0{idx}T10:00:00.000+0000",
            "updated": f"2024-01-0{idx}T12:00:00.000+0000",
            "resolutiondate": None,
            "project": {"key": "PORT"},
            "parent": None,
            "subtasks": [],
            "assignee": {"accountId": f"assignee-account-{idx}"},
            "reporter": {"accountId": f"reporter-account-{idx}"},
        },
    }


def issues_page_response() -> dict[str, Any]:
    return {
        "issues": [issue_response(i) for i in range(1, ISSUE_COUNT + 1)],
        # No nextPageToken → single page, pagination stops.
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def user_response(idx: int) -> dict[str, Any]:
    return {
        "accountId": f"user-account-{idx}",
        "displayName": f"User {idx}",
        "emailAddress": f"user{idx}@test.com",
        "active": True,
        "accountType": "atlassian",
        "timeZone": "UTC",
        "locale": "en_US",
        "avatarUrls": {
            "48x48": f"https://avatar.example.com/user{idx}.png",
        },
    }


def users_page_response() -> list[dict[str, Any]]:
    return [user_response(i) for i in range(1, USER_COUNT + 1)]
