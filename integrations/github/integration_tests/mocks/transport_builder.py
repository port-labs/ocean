import json
from collections.abc import Callable
from typing import Any

import httpx

from port_ocean.integration_testing import InterceptTransport

from mocks.payloads import (
    INSTALLATION_ID,
    ORG_LOGIN,
    REPO_NAMES,
    branch_response,
    code_scanning_alert_response,
    collaborator_response,
    dependabot_alert_response,
    deployment_response,
    environment_list_response,
    issue_response,
    org_response,
    release_response,
    repo_response,
    secret_scanning_alert_response,
    tag_response,
    workflow_list_response,
)


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

    def with_collaborator_routes(self) -> "GithubMockTransportBuilder":
        self._add_per_repo_route("collaborators", collaborator_response)
        return self

    def add_graphql_route(
        self,
        query_substring: str,
        response: dict[str, Any],
    ) -> "GithubMockTransportBuilder":
        def matches(request: httpx.Request) -> bool:
            if "/graphql" not in str(request.url):
                return False
            if not request.content:
                return False
            body = json.loads(request.content)
            return query_substring in body.get("query", "")

        self._transport.add_route("POST", matches, response)
        return self

    def build(self, *, strict: bool = True) -> InterceptTransport:
        self._transport.strict = strict
        return self._transport
