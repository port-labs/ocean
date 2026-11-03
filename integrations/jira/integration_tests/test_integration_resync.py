import os
from typing import Any

import pytest
from port_ocean.integration_testing import (
    BaseIntegrationTest,
    InterceptTransport,
    ResyncResult,
)

from helpers import integration_config, mapping_for_kind
from mocks.payloads import (
    JIRA_API_URL,
    JIRA_HOST,
    ISSUE_COUNT,
    PROJECT_KEYS,
    USER_COUNT,
    issue_response,
    issues_page_response,
    project_response,
    projects_page_response,
    user_response,
    users_page_response,
)


class TestJiraHappyPath(BaseIntegrationTest):
    """Happy-path integration test for the Jira integration.

    Exercises a full resync across the three default kinds at once and checks
    the raw records handed to Port for each kind:
    - project → 2 projects keyed by `key`
    - issue   → 2 issues keyed by `key` (with project/assignee/reporter fields)
    - user    → 2 users keyed by `accountId`
    """

    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    def create_third_party_transport(self) -> InterceptTransport:
        t = InterceptTransport(strict=True)

        # Projects: single page, total=len → pagination stops after one request.
        t.add_route(
            "GET",
            f"{JIRA_API_URL}/project/search",
            {"status_code": 200, "json": projects_page_response()},
        )

        # Issues: POST with token-based pagination; no nextPageToken → single page.
        t.add_route(
            "POST",
            f"{JIRA_API_URL}/search/jql",
            {"status_code": 200, "json": issues_page_response()},
        )

        # Users: raw list pagination — page 1 returns users, page 2 returns []
        # which breaks the pagination loop.
        t.add_route(
            "GET",
            f"{JIRA_API_URL}/users/search",
            {"status_code": 200, "json": users_page_response()},
            times=1,
        )
        t.add_route(
            "GET",
            f"{JIRA_API_URL}/users/search",
            {"status_code": 200, "json": []},
        )

        return t

    def create_mapping_config(self) -> dict[str, Any]:
        return mapping_for_kind("project", "issue", "user")

    def create_integration_config(self) -> dict[str, Any]:
        return integration_config()

    @pytest.mark.asyncio
    async def test_happy_path(self, resync: ResyncResult) -> None:
        assert resync.errors == [], f"Resync had errors: {resync.errors}"
        assert resync.reconciliation_success is True

        # --- Projects ---
        projects = resync.raw_items("project")
        assert len(projects) == len(
            PROJECT_KEYS
        ), f"Expected {len(PROJECT_KEYS)} projects, got {len(projects)}"
        projects_by_key = {p["key"]: p for p in projects}
        for i, key in enumerate(PROJECT_KEYS, start=1):
            record = project_response(key, i)
            project = projects_by_key[key]
            assert project["name"] == record["name"]
            assert project["self"].startswith(JIRA_HOST)
            assert (
                project["insight"]["totalIssueCount"]
                == record["insight"]["totalIssueCount"]
            )

        # --- Issues ---
        issues = resync.raw_items("issue")
        assert (
            len(issues) == ISSUE_COUNT
        ), f"Expected {ISSUE_COUNT} issues, got {len(issues)}"
        issues_by_key = {i["key"]: i for i in issues}
        for i in range(1, ISSUE_COUNT + 1):
            record = issue_response(i)
            issue = issues_by_key[record["key"]]
            assert issue["self"].startswith(JIRA_HOST)
            fields = issue["fields"]
            expected = record["fields"]
            assert fields["summary"] == expected["summary"]
            assert fields["status"]["name"] == expected["status"]["name"]
            assert fields["issuetype"]["name"] == expected["issuetype"]["name"]
            assert (
                fields["creator"]["emailAddress"] == expected["creator"]["emailAddress"]
            )
            assert fields["priority"]["name"] == expected["priority"]["name"]
            assert fields["labels"] == expected["labels"]
            assert fields["project"]["key"] == expected["project"]["key"]
            assert fields["assignee"]["accountId"] == expected["assignee"]["accountId"]
            assert fields["reporter"]["accountId"] == expected["reporter"]["accountId"]

        # --- Users ---
        users = resync.raw_items("user")
        assert (
            len(users) == USER_COUNT
        ), f"Expected {USER_COUNT} users, got {len(users)}"
        users_by_id = {u["accountId"]: u for u in users}
        for i in range(1, USER_COUNT + 1):
            record = user_response(i)
            user = users_by_id[record["accountId"]]
            assert user["displayName"] == record["displayName"]
            assert user["emailAddress"] == record["emailAddress"]
            assert user["active"] == record["active"]
            assert user["accountType"] == record["accountType"]
            assert user["timeZone"] == record["timeZone"]
            assert user["locale"] == record["locale"]
            assert user["avatarUrls"]["48x48"] == record["avatarUrls"]["48x48"]
