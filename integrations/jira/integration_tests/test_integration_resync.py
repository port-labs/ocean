import os
from typing import Any

import pytest
from port_ocean.integration_testing import (
    BaseIntegrationTest,
    InterceptTransport,
    ResyncResult,
)

from mocks.payloads import (
    JIRA_API_URL,
    JIRA_EMAIL,
    JIRA_HOST,
    JIRA_TOKEN,
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

    Exercises a full resync across the three default kinds at once:
    - project → jiraProject entities
    - issue   → jiraIssue entities (with project/assignee/reporter relations)
    - user    → jiraUser entities

    Expected output: 2 projects, 2 issues, 2 users — with identifiers,
    titles, and key properties all verified.
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
        return {
            "createMissingRelatedEntities": True,
            "deleteDependentEntities": True,
            "resources": [
                {
                    "kind": "project",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".key",
                                "title": ".name",
                                "blueprint": '"jiraProject"',
                                "properties": {
                                    "url": '(.self | split("/") | .[:3] | join("/")) + "/projects/" + .key',
                                    "totalIssues": ".insight.totalIssueCount",
                                },
                            }
                        }
                    },
                },
                {
                    "kind": "issue",
                    "selector": {
                        "query": "true",
                        "jql": "project = PORT",
                    },
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".key",
                                "title": ".fields.summary",
                                "blueprint": '"jiraIssue"',
                                "properties": {
                                    "url": '(.self | split("/") | .[:3] | join("/")) + "/browse/" + .key',
                                    "status": ".fields.status.name",
                                    "issueType": ".fields.issuetype.name",
                                    "creator": ".fields.creator.emailAddress",
                                    "priority": ".fields.priority.name",
                                    "labels": ".fields.labels",
                                    "created": ".fields.created",
                                    "updated": ".fields.updated",
                                },
                                "relations": {
                                    "project": ".fields.project.key",
                                    "assignee": ".fields.assignee.accountId",
                                    "reporter": ".fields.reporter.accountId",
                                },
                            }
                        }
                    },
                },
                {
                    "kind": "user",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".accountId",
                                "title": ".displayName",
                                "blueprint": '"jiraUser"',
                                "properties": {
                                    "emailAddress": ".emailAddress",
                                    "active": ".active",
                                    "accountType": ".accountType",
                                    "timeZone": ".timeZone",
                                    "locale": ".locale",
                                    "avatarUrl": '.avatarUrls["48x48"]',
                                },
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-jira",
                "type": "jira",
                "config": {
                    "jira_host": JIRA_HOST,
                    "atlassian_user_email": JIRA_EMAIL,
                    "atlassian_user_token": JIRA_TOKEN,
                },
            }
        }

    @pytest.mark.asyncio
    async def test_happy_path(self, resync: ResyncResult) -> None:
        assert resync.errors == [], f"Resync had errors: {resync.errors}"
        assert resync.reconciliation_success is True

        by_blueprint: dict[str, list[dict[str, Any]]] = {}
        for entity in resync.upserted_entities:
            by_blueprint.setdefault(entity["blueprint"], []).append(entity)

        # --- Projects ---
        projects = by_blueprint.get("jiraProject", [])
        assert len(projects) == len(PROJECT_KEYS), (
            f"Expected {len(PROJECT_KEYS)} projects, got {len(projects)}"
        )
        projects_by_id = {e["identifier"]: e for e in projects}
        for i, key in enumerate(PROJECT_KEYS, start=1):
            record = project_response(key, i)
            entity = projects_by_id[key]
            assert entity["title"] == record["name"]
            assert entity["properties"]["url"] == f"{JIRA_HOST}/projects/{key}"
            assert entity["properties"]["totalIssues"] == record["insight"]["totalIssueCount"]

        # --- Issues ---
        issues = by_blueprint.get("jiraIssue", [])
        assert len(issues) == ISSUE_COUNT, (
            f"Expected {ISSUE_COUNT} issues, got {len(issues)}"
        )
        issues_by_id = {e["identifier"]: e for e in issues}
        for i in range(1, ISSUE_COUNT + 1):
            record = issue_response(i)
            key = record["key"]
            entity = issues_by_id[key]
            assert entity["title"] == record["fields"]["summary"]
            props = entity["properties"]
            assert props["url"] == f"{JIRA_HOST}/browse/{key}"
            assert props["status"] == record["fields"]["status"]["name"]
            assert props["issueType"] == record["fields"]["issuetype"]["name"]
            assert props["creator"] == record["fields"]["creator"]["emailAddress"]
            assert props["priority"] == record["fields"]["priority"]["name"]
            assert props["labels"] == record["fields"]["labels"]
            assert entity["relations"]["project"] == record["fields"]["project"]["key"]
            assert entity["relations"]["assignee"] == record["fields"]["assignee"]["accountId"]
            assert entity["relations"]["reporter"] == record["fields"]["reporter"]["accountId"]

        # --- Users ---
        users = by_blueprint.get("jiraUser", [])
        assert len(users) == USER_COUNT, (
            f"Expected {USER_COUNT} users, got {len(users)}"
        )
        users_by_id = {e["identifier"]: e for e in users}
        for i in range(1, USER_COUNT + 1):
            record = user_response(i)
            entity = users_by_id[record["accountId"]]
            assert entity["title"] == record["displayName"]
            props = entity["properties"]
            assert props["emailAddress"] == record["emailAddress"]
            assert props["active"] == record["active"]
            assert props["accountType"] == record["accountType"]
            assert props["timeZone"] == record["timeZone"]
            assert props["locale"] == record["locale"]
            assert props["avatarUrl"] == record["avatarUrls"]["48x48"]
