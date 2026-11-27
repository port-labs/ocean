from collections.abc import Callable

import httpx

from port_ocean.integration_testing import InterceptTransport

from mocks.payloads import (
    JIRA_API_URL,
    SITE_ID,
    TEAM_COUNT,
    TEAMS_API_PATH,
    TENANT_INFO_URL,
    issues_page_response,
    projects_page_response,
    site_id_required_response,
    team_id,
    team_members_page_response,
    teams_page_response,
    users_page_response,
)


def _has_site_id(request: httpx.Request) -> bool:
    return request.url.params.get("siteId") == SITE_ID


def _is_teams_list(request: httpx.Request) -> bool:
    return request.url.path == TEAMS_API_PATH


def _team_members_matcher(
    idx: int, *, with_site_id: bool
) -> Callable[[httpx.Request], bool]:
    members_path = f"{TEAMS_API_PATH}/{team_id(idx)}/members"

    def matches(request: httpx.Request) -> bool:
        if request.url.path != members_path:
            return False
        return _has_site_id(request) if with_site_id else True

    return matches


class JiraMockTransportBuilder:
    """Builds a fake Jira REST API transport for integration tests.

    Each resync kind maps to one or more HTTP routes:

    - project  → GET  /rest/api/3/project/search   (offset-based, single page)
    - issue    → POST /rest/api/3/search/jql        (token-based, single page)
    - user     → GET  /rest/api/3/users/search      (offset-based, 2 pages needed:
                                                      page 1 returns users, page 2
                                                      returns [] to stop pagination)
    """

    def __init__(self) -> None:
        self._transport = InterceptTransport(strict=True)

    def with_project_routes(self) -> "JiraMockTransportBuilder":
        self._transport.add_route(
            "GET",
            f"{JIRA_API_URL}/project/search",
            {"status_code": 200, "json": projects_page_response()},
        )
        return self

    def with_issue_routes(self) -> "JiraMockTransportBuilder":
        self._transport.add_route(
            "POST",
            f"{JIRA_API_URL}/search/jql",
            {"status_code": 200, "json": issues_page_response()},
        )
        return self

    def with_user_routes(self) -> "JiraMockTransportBuilder":
        # Page 1: returns the actual users.
        self._transport.add_route(
            "GET",
            f"{JIRA_API_URL}/users/search",
            {"status_code": 200, "json": users_page_response()},
            times=1,
        )
        # Page 2+: empty list stops the offset-based pagination loop.
        # (users API returns a raw list with no "total" key, so the paginator
        # keeps requesting until it gets an empty response.)
        self._transport.add_route(
            "GET",
            f"{JIRA_API_URL}/users/search",
            {"status_code": 200, "json": []},
        )
        return self

    def with_team_routes(self) -> "JiraMockTransportBuilder":
        """Fake the Atlassian Teams API the way it behaves today.

        Calls without the Jira site's cloud ID as ``siteId`` are rejected with
        400, so a regression that stops sending it fails the resync.

        - team    → GET  /gateway/api/public/teams/v1/org/<org>/teams?siteId=...
        - members → POST /gateway/api/public/teams/v1/org/<org>/teams/<id>/members?siteId=...
        - site ID → GET  /_edge/tenant_info (public, no credentials needed)
        """
        self._transport.add_route(
            "GET",
            TENANT_INFO_URL,
            {"status_code": 200, "json": {"cloudId": SITE_ID}},
        )

        self._transport.add_route(
            "GET",
            lambda r: _is_teams_list(r) and _has_site_id(r),
            {"status_code": 200, "json": teams_page_response()},
        )
        self._transport.add_route("GET", _is_teams_list, site_id_required_response())

        for idx in range(1, TEAM_COUNT + 1):
            self._transport.add_route(
                "POST",
                _team_members_matcher(idx, with_site_id=True),
                {"status_code": 200, "json": team_members_page_response(idx)},
            )
            self._transport.add_route(
                "POST",
                _team_members_matcher(idx, with_site_id=False),
                site_id_required_response(),
            )
        return self

    def build(self, *, strict: bool = True) -> InterceptTransport:
        self._transport.strict = strict
        return self._transport
