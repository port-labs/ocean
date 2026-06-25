import json
from typing import Any

import httpx

from port_ocean.integration_testing import InterceptTransport

from mocks.payloads import (
    INSTALLATION_ID,
    ORG_LOGIN,
    REPO_NAMES,
    issue_response,
    org_response,
    release_response,
    repo_response,
)


class GithubMockTransportBuilder:
    """Builds a fake GitHub API transport with reusable base routes."""

    def __init__(self) -> None:
        self._transport = InterceptTransport(strict=True)

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
        for i, name in enumerate(REPO_NAMES, start=1):
            self._transport.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/issues",
                {"status_code": 200, "json": [issue_response(name, i)]},
            )
        return self

    def with_release_routes(self) -> "GithubMockTransportBuilder":
        for i, name in enumerate(REPO_NAMES, start=1):
            self._transport.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/releases",
                {"status_code": 200, "json": [release_response(name, i)]},
            )
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
