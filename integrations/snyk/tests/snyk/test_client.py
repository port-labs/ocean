import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from typing import Any, Dict, List, Generator
from snyk.client import SnykClient
from snyk.overrides import SnykProjectAPIQueryParams, SnykVulnerabilityAPIQueryParams
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext
from aiolimiter import AsyncLimiter
import time
import asyncio

MOCK_API_URL = "https://api.snyk.io/v1"
MOCK_TOKEN = "dummy_token"
MOCK_PROJECT_ID = "12345"
MOCK_ISSUES = [{"id": "issue1"}, {"id": "issue2"}]
MOCK_ORG_URL = "https://your_organization_url.com"
MOCK_PERSONAL_ACCESS_TOKEN = "personal_access_token"


# Port Ocean Mocks
@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": MOCK_PERSONAL_ACCESS_TOKEN,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    """Fixture to mock the event context."""
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


@pytest.fixture
def snyk_client() -> SnykClient:
    """Fixture to create a SnykClient instance for testing."""
    return SnykClient(
        token=MOCK_TOKEN,
        api_url=MOCK_API_URL,
        app_host=None,
        organization_ids=None,
        group_ids=None,
        webhook_secret=None,
        rate_limiter=AsyncLimiter(5, 1),
    )


@pytest.mark.asyncio
async def test_send_api_request_rate_limit(snyk_client: SnykClient) -> None:
    """Test rate limit enforcement on API request."""
    with patch.object(
        snyk_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value.json = AsyncMock(return_value={})
        mock_request.return_value.raise_for_status = AsyncMock()

        async def make_request() -> None:
            await snyk_client._send_api_request(url=f"{MOCK_API_URL}/test")
            await mock_request.return_value.raise_for_status()

        start_time = time.monotonic()

        await asyncio.gather(*[make_request() for _ in range(15)])

        elapsed_time = time.monotonic() - start_time

        assert (
            elapsed_time >= 1.0
        ), "Rate limiter did not properly enforce the rate limit."


@pytest.mark.asyncio
async def test_get_paginated_resources(
    snyk_client: SnykClient, mock_event_context: MagicMock
) -> None:
    """Test getting paginated resources with mocked response."""

    async def mock_send_api_request(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        url = kwargs.get("url")
        if url and url.endswith("/page1"):
            return {
                "data": [{"id": "item1"}],
                "links": {
                    "next": "/rest/page2?version=2024-06-21&meta.latest_issue_counts=true&expand=target&limit=50&starting_after=v1.eyJpZCI6ODI3MzI3NjR9"
                },
            }
        elif url and "/rest/page2" in url:
            return {"data": [{"id": "item2"}], "links": {"next": ""}}
        return {}

    with patch.object(
        snyk_client, "_send_api_request", side_effect=mock_send_api_request
    ):
        url_path = "/page1"

        resources: List[Dict[str, Any]] = []
        async for resource_batch in snyk_client._get_paginated_resources(
            url_path=url_path
        ):
            resources.extend(resource_batch)

        assert resources == [{"id": "item1"}, {"id": "item2"}]


@pytest.mark.asyncio
async def test_get_paginated_issues_with_project_params_fetches_issues_per_project(
    snyk_client: SnykClient, mock_event_context: MagicMock
) -> None:
    """project_params routes fetching through matching projects, not the org-level endpoint."""
    mock_org = {"id": "org-1"}
    mock_project = {"id": "proj-1", "type": "npm"}
    mock_issues = [{"id": "issue-1"}, {"id": "issue-2"}]
    project_params = SnykProjectAPIQueryParams(origins=["github"])

    captured_api_params: list[Any] = []

    async def mock_get_paginated_projects(
        org: dict[str, Any], api_params: Any = None, enrich_with_org: bool = True
    ) -> Any:
        captured_api_params.append(api_params)
        yield [mock_project]

    async def mock_get_project_vulnerabilities(
        org_id: str, project: dict[str, Any], query_params: dict[str, Any]
    ) -> Any:
        yield mock_issues

    with (
        patch.object(
            snyk_client, "get_paginated_projects", new=mock_get_paginated_projects
        ),
        patch.object(
            snyk_client,
            "get_project_vulnerabilities",
            new=mock_get_project_vulnerabilities,
        ),
    ):
        results = []
        async for batch in snyk_client.get_paginated_issues(
            org=mock_org, project_params=project_params
        ):
            results.extend(batch)

    assert len(results) == 2
    assert all(r["__organization"] == mock_org for r in results)
    assert len(captured_api_params) == 1
    assert captured_api_params[0] == project_params


@pytest.mark.asyncio
async def test_get_paginated_issues_merges_api_params_with_base_version(
    snyk_client: SnykClient, mock_event_context: MagicMock
) -> None:
    """api_params are merged with the base version param before being forwarded to get_project_vulnerabilities."""
    mock_org = {"id": "org-1"}
    mock_project = {"id": "proj-1", "type": "npm"}
    api_params = SnykVulnerabilityAPIQueryParams(status=["open"])
    project_params = SnykProjectAPIQueryParams()

    captured_query_params: list[dict[str, Any]] = []

    async def mock_get_paginated_projects(
        org: dict[str, Any], api_params: Any = None, enrich_with_org: bool = True
    ) -> Any:
        yield [mock_project]

    async def mock_get_project_vulnerabilities(
        org_id: str, project: dict[str, Any], query_params: dict[str, Any]
    ) -> Any:
        captured_query_params.append(query_params)
        yield []

    with (
        patch.object(
            snyk_client, "get_paginated_projects", new=mock_get_paginated_projects
        ),
        patch.object(
            snyk_client,
            "get_project_vulnerabilities",
            new=mock_get_project_vulnerabilities,
        ),
    ):
        async for _ in snyk_client.get_paginated_issues(
            org=mock_org, project_params=project_params, api_params=api_params
        ):
            pass

    assert len(captured_query_params) == 1
    params = captured_query_params[0]
    assert params["version"] == snyk_client.snyk_api_version
    assert params["status"] == ["open"]


@pytest.mark.asyncio
async def test_get_paginated_issues_without_project_params_uses_org_endpoint(
    snyk_client: SnykClient, mock_event_context: MagicMock
) -> None:
    """Without project_params or attach_project, issues are fetched directly from the org issues endpoint."""
    mock_org = {"id": "org-1"}
    mock_issues = [{"id": "issue-1"}]
    expected_url = f"/orgs/{mock_org['id']}/issues"

    captured_urls: list[str] = []

    async def mock_get_paginated_resources(
        url_path: str, query_params: Any = None
    ) -> Any:
        captured_urls.append(url_path)
        yield mock_issues

    with (
        patch.object(
            snyk_client, "_get_paginated_resources", new=mock_get_paginated_resources
        ),
        patch.object(snyk_client, "get_paginated_projects") as mock_get_projects,
    ):
        results = []
        async for batch in snyk_client.get_paginated_issues(org=mock_org):
            results.extend(batch)

    assert captured_urls == [expected_url]
    assert len(results) == 1
    assert results[0]["__organization"] == mock_org
    mock_get_projects.assert_not_called()


@pytest.mark.asyncio
async def test_get_single_target_should_not_fetch_projects_when_attach_flag_is_false(
    snyk_client: SnykClient,
) -> None:
    mock_org = {"id": "047f3b54-6997-402c-80b6-193496030c25"}

    mocked_project_id = "76191494-b77a-422f-8700-1f952136009a"
    mock_project = {
        "id": mocked_project_id,
        "relationships": {"target": {"data": {"id": "target-id"}}},
    }

    with (
        patch.object(
            snyk_client, "get_single_project", AsyncMock(return_value=mock_project)
        ),
        patch.object(
            snyk_client,
            "_send_api_request",
            AsyncMock(return_value={"data": {"id": "target-id"}}),
        ),
        patch.object(snyk_client, "get_paginated_projects") as mock_pag,
    ):

        await snyk_client.get_single_target_by_project_id(
            mock_org, mocked_project_id, attach_project_data=False
        )

        mock_pag.assert_not_called()


@pytest.mark.asyncio
async def test_get_single_target_by_project_id_should_gracefully_handle_missing_target_link(
    snyk_client: SnykClient,
) -> None:
    mock_org = {"id": "047f3b54-6997-402c-80b6-193496030c25"}

    mocked_project_id = "76191494-b77a-422f-8700-1f952136009a"
    mock_project = {"id": mocked_project_id, "relationships": {}}

    with patch.object(
        snyk_client, "get_single_project", AsyncMock(return_value=mock_project)
    ):
        result = await snyk_client.get_single_target_by_project_id(
            mock_org, mocked_project_id, attach_project_data=False
        )
        assert result == {}
