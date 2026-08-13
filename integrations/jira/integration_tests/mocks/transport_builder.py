from port_ocean.integration_testing import InterceptTransport

from mocks.payloads import (
    JIRA_API_URL,
    issues_page_response,
    projects_page_response,
    users_page_response,
)


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

    def build(self, *, strict: bool = True) -> InterceptTransport:
        self._transport.strict = strict
        return self._transport
