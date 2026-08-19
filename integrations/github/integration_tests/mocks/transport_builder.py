import json
from collections.abc import Callable
from typing import Any

import httpx

from port_ocean.integration_testing import InterceptTransport

from mocks.graphql_payloads import (
    org_members_graphql_response,
    pull_requests_graphql_response,
    team_with_members_graphql_response,
)
from mocks.payloads import (
    DEFAULT_BRANCH_NAME,
    INSTALLATION_ID,
    ORG_LOGIN,
    REPO_NAMES,
    branch_detail_response,
    branch_protection_response,
    branch_response,
    code_scanning_alert_response,
    collaborator_response,
    dependabot_alert_response,
    deployment_id_for_index,
    deployment_response,
    deployment_status_response,
    environment_list_response,
    issue_response,
    org_response,
    release_response,
    repo_response,
    secret_scanning_alert_response,
    tag_response,
    teams_list_response,
    workflow_id_for_index,
    workflow_list_response,
    workflow_run_list_response,
)

GRAPHQL_UNKNOWN_ERROR: dict[str, Any] = {
    "errors": [{"message": "something went wrong", "type": "UNKNOWN"}]
}


def _query_of(request: httpx.Request) -> str:
    if "/graphql" not in str(request.url) or not request.content:
        return ""
    return json.loads(request.content).get("query", "")


def _query_variables(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content).get("variables", {})


def _query_has(request: httpx.Request, field: str) -> bool:
    return field in _query_of(request)


def _is_list_prs_query(request: httpx.Request) -> bool:
    return "ListPullRequests" in _query_of(request)


def _is_pr_details_query(request: httpx.Request) -> bool:
    return "PullRequestDetails" in _query_of(request)


class GithubMockTransportBuilder:
    """Builds a fake GitHub API transport with reusable base routes."""

    def __init__(self) -> None:
        self._transport = InterceptTransport(strict=True)

    def _add_per_repo_route(
        self,
        path_suffix: str,
        response_for_repo: Callable[[str, int], Any],
    ) -> None:
        for i, name in enumerate(REPO_NAMES, start=1):
            self._transport.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/{path_suffix}",
                {"status_code": 200, "json": response_for_repo(name, i)},
            )

    def with_base(self) -> "GithubMockTransportBuilder":
        """Auth, organization, and repository list routes shared by all kinds."""
        self._transport.add_route(
            "GET",
            f"/users/{ORG_LOGIN}/installation",
            {
                "status_code": 200,
                "json": {"id": INSTALLATION_ID, "account": org_response()},
            },
        )
        self._transport.add_route(
            "POST",
            f"/app/installations/{INSTALLATION_ID}/access_tokens",
            {
                "status_code": 201,
                "json": {
                    "token": "ghs_test_token",
                    "expires_at": "2099-12-31T23:59:59Z",
                    "permissions": {"contents": "read", "metadata": "read"},
                    "repository_selection": "all",
                },
            },
        )
        self._transport.add_route(
            "GET",
            f"/users/{ORG_LOGIN}",
            {"status_code": 200, "json": org_response()},
        )

        repos = [repo_response(name, i) for i, name in enumerate(REPO_NAMES)]
        self._transport.add_route(
            "GET",
            f"/orgs/{ORG_LOGIN}/repos",
            {"status_code": 200, "json": repos},
        )
        return self

    def with_issue_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route(
            "issues",
            lambda name, i: [issue_response(name, i)],
        )
        return self

    def with_release_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route(
            "releases",
            lambda name, i: [release_response(name, i)],
        )
        return self

    def with_tag_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route(
            "tags",
            lambda name, i: [tag_response(name, i)],
        )
        return self

    def with_environment_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route("environments", environment_list_response)
        return self

    def with_workflow_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route("actions/workflows", workflow_list_response)
        return self

    def with_branch_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route("branches", branch_response)
        return self

    def with_branch_protection_routes(self) -> "GithubMockTransportBuilder":
        for i, name in enumerate(REPO_NAMES, start=1):
            self._transport.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/branches/{DEFAULT_BRANCH_NAME}/protection",
                {
                    "status_code": 200,
                    "json": branch_protection_response(name, i),
                },
            )
        self._add_per_repo_route("branches", branch_response)
        return self

    def with_branch_detailed_routes(self) -> "GithubMockTransportBuilder":
        for i, name in enumerate(REPO_NAMES, start=1):
            self._transport.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/branches/{DEFAULT_BRANCH_NAME}",
                {
                    "status_code": 200,
                    "json": branch_detail_response(name, i),
                },
            )
        self._add_per_repo_route("branches", branch_response)
        return self

    def with_dependabot_alert_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route("dependabot/alerts", dependabot_alert_response)
        return self

    def with_code_scanning_alert_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route(
            "code-scanning/alerts",
            code_scanning_alert_response,
        )
        return self

    def with_secret_scanning_alert_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route(
            "secret-scanning/alerts",
            secret_scanning_alert_response,
        )
        return self

    def with_deployment_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route("deployments", deployment_response)
        return self

    def with_deployment_status_routes(self) -> "GithubMockTransportBuilder":
        for i, name in enumerate(REPO_NAMES, start=1):
            deployment_id = deployment_id_for_index(i)
            self._transport.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/deployments/{deployment_id}/statuses",
                {
                    "status_code": 200,
                    "json": deployment_status_response(name, i),
                },
            )
        self._add_per_repo_route("deployments", deployment_response)
        return self

    def with_workflow_run_routes(self) -> "GithubMockTransportBuilder":
        for i, name in enumerate(REPO_NAMES, start=1):
            workflow_id = workflow_id_for_index(i)
            self._transport.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/actions/workflows/{workflow_id}/runs",
                {
                    "status_code": 200,
                    "json": workflow_run_list_response(name, i),
                },
            )
        self._add_per_repo_route("actions/workflows", workflow_list_response)
        return self

    def with_collaborator_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route("collaborators", collaborator_response)
        return self

    def with_user_routes(self) -> "GithubMockTransportBuilder":
        self.add_graphql_route("OrgMemberQuery", org_members_graphql_response)
        return self

    def with_team_routes(self) -> "GithubMockTransportBuilder":
        self._transport.add_route(
            "GET",
            f"/orgs/{ORG_LOGIN}/teams",
            {"status_code": 200, "json": teams_list_response()},
        )
        self.add_graphql_route("getTeam", team_with_members_graphql_response)
        return self

    def with_pull_request_graphql_routes(self) -> "GithubMockTransportBuilder":
        self.add_graphql_route("ListPullRequests", pull_requests_graphql_response)
        return self

    def add_graphql_route(
        self,
        query_substring: str,
        response: dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any]],
    ) -> "GithubMockTransportBuilder":
        def matches(request: httpx.Request) -> bool:
            if "/graphql" not in str(request.url):
                return False
            if not request.content:
                return False
            body = json.loads(request.content)
            return query_substring in body.get("query", "")

        def build_response(request: httpx.Request) -> dict[str, Any]:
            if callable(response):
                body = json.loads(request.content)
                payload = response(body.get("variables", {}))
            else:
                payload = response
            return {"status_code": 200, "json": payload}

        self._transport.add_route("POST", matches, build_response)
        return self

    def fail_list_prs_when_query_has(self, field: str) -> "GithubMockTransportBuilder":
        """Answer list-PR queries that still carry ``field`` with an unknown error.

        Simulates a query being too heavy while it selects ``field``; chain
        ``succeed_list_prs`` after this so a query with the field stripped wins.
        """
        self._transport.add_route(
            "POST",
            lambda r: _is_list_prs_query(r) and _query_has(r, field),
            {"status_code": 200, "json": GRAPHQL_UNKNOWN_ERROR},
        )
        return self

    def fail_all_list_prs(self) -> "GithubMockTransportBuilder":
        """Answer every list-PR query with an unknown error (no fallback recovers)."""
        self._transport.add_route(
            "POST",
            _is_list_prs_query,
            {"status_code": 200, "json": GRAPHQL_UNKNOWN_ERROR},
        )
        return self

    def succeed_list_prs(self) -> "GithubMockTransportBuilder":
        """Answer any remaining list-PR query with the standard PR payload."""
        self._transport.add_route(
            "POST",
            _is_list_prs_query,
            lambda r: {
                "status_code": 200,
                "json": pull_requests_graphql_response(_query_variables(r)),
            },
        )
        return self

    def respond_pr_details(
        self, pull_request: dict[str, Any]
    ) -> "GithubMockTransportBuilder":
        """Answer single-PR detail (field backfill) queries with ``pull_request``."""
        self._transport.add_route(
            "POST",
            _is_pr_details_query,
            {
                "status_code": 200,
                "json": {"data": {"repository": {"pullRequest": pull_request}}},
            },
        )
        return self

    def build(self, *, strict: bool = True) -> InterceptTransport:
        self._transport.strict = strict
        return self._transport
