from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from jira.client import JiraClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "jira_host": "https://getport.atlassian.net",
            "atlassian_user_email": "jira@atlassian.net",
            "atlassian_user_token": "asdf",
            "atlassian_organisation_id": "asdf",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.load_external_oauth_access_token = MagicMock(return_value=None)
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_jira_client() -> JiraClient:
    """Fixture to initialize JiraClient with mock parameters."""
    return JiraClient(
        jira_url="https://example.atlassian.net",
        jira_email="test@example.com",
        jira_token="test_token",
    )


@pytest.mark.asyncio
async def test_jsm_client_initialization(mock_jira_client: JiraClient) -> None:
    """Test that JSM API URLs are correctly initialized."""
    assert (
        mock_jira_client.jsm_api_url
        == "https://example.atlassian.net/rest/servicedeskapi"
    )
    assert (
        mock_jira_client.jsm_insight_api_url
        == "https://example.atlassian.net/rest/insight/1.0"
    )
    assert (
        mock_jira_client.jsm_opsgenie_api_url
        == "https://example.atlassian.net/rest/api/2/opsgenie"
    )


@pytest.mark.asyncio
async def test_get_paginated_service_desks(mock_jira_client: JiraClient) -> None:
    """Test getting paginated service desks from JSM."""
    mock_response_data = {
        "values": [
            {"id": "1", "projectKey": "SD", "serviceDeskName": "Service Desk 1"},
            {"id": "2", "projectKey": "IT", "serviceDeskName": "IT Help Desk"},
        ],
        "isLastPage": True,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ) as mock_request:
        service_desks = []
        async for batch in mock_jira_client.get_paginated_service_desks():
            service_desks.extend(batch)

        assert len(service_desks) == 2
        assert service_desks[0]["serviceDeskName"] == "Service Desk 1"
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_get_paginated_requests(mock_jira_client: JiraClient) -> None:
    """Test getting paginated customer requests from JSM."""
    mock_response_data = {
        "values": [
            {"issueId": "10001", "serviceDeskId": "1", "requestTypeId": "1"},
            {"issueId": "10002", "serviceDeskId": "1", "requestTypeId": "2"},
        ],
        "isLastPage": True,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ):
        requests = []
        async for batch in mock_jira_client.get_paginated_requests(service_desk_id="1"):
            requests.extend(batch)

        assert len(requests) == 2
        assert requests[0]["issueId"] == "10001"


@pytest.mark.asyncio
async def test_get_paginated_incidents(mock_jira_client: JiraClient) -> None:
    """Test getting paginated incidents from JSM."""
    mock_response_data = {
        "data": [
            {"id": "incident-1", "status": "open", "title": "Database issue"},
            {"id": "incident-2", "status": "resolved", "title": "Network problem"},
        ],
        "paging": {"next": None},
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ):
        incidents = []
        async for batch in mock_jira_client.get_paginated_incidents():
            incidents.extend(batch)

        assert len(incidents) == 2
        assert incidents[0]["title"] == "Database issue"


@pytest.mark.asyncio
async def test_get_paginated_assets(mock_jira_client: JiraClient) -> None:
    """Test getting paginated assets from JSM Insight."""
    mock_response_data = {
        "objectEntries": [
            {
                "id": "asset-1",
                "objectType": {"name": "Server"},
                "name": "web-server-01",
            },
            {
                "id": "asset-2",
                "objectType": {"name": "Database"},
                "name": "db-server-01",
            },
        ],
        "isLast": True,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ):
        assets = []
        async for batch in mock_jira_client.get_paginated_assets(schema_id="1"):
            assets.extend(batch)

        assert len(assets) == 2
        assert assets[0]["name"] == "web-server-01"


@pytest.mark.asyncio
async def test_get_paginated_schedules(mock_jira_client: JiraClient) -> None:
    """Test getting paginated schedules from JSM."""
    mock_response_data = {
        "data": [
            {"id": "schedule-1", "name": "On-call Schedule 1", "timezone": "UTC"},
            {"id": "schedule-2", "name": "Weekend Schedule", "timezone": "PST"},
        ],
        "paging": {"next": None},
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ):
        schedules = []
        async for batch in mock_jira_client.get_paginated_schedules():
            schedules.extend(batch)

        assert len(schedules) == 2
        assert schedules[0]["name"] == "On-call Schedule 1"


@pytest.mark.asyncio
async def test_get_single_service_desk(mock_jira_client: JiraClient) -> None:
    """Test getting a single service desk by ID."""
    mock_response_data = {
        "id": "1",
        "projectKey": "SD",
        "serviceDeskName": "Service Desk 1",
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ) as mock_request:
        service_desk = await mock_jira_client.get_single_service_desk("1")

        assert service_desk["serviceDeskName"] == "Service Desk 1"
        mock_request.assert_called_once_with(
            "GET", "https://example.atlassian.net/rest/servicedeskapi/servicedesk/1"
        )


@pytest.mark.asyncio
async def test_get_single_request(mock_jira_client: JiraClient) -> None:
    """Test getting a single customer request by issue ID."""
    mock_response_data = {
        "issueId": "10001",
        "serviceDeskId": "1",
        "requestTypeId": "1",
        "currentStatus": {"status": "Waiting for support"},
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ) as mock_request:
        request = await mock_jira_client.get_single_request("10001")

        assert request["issueId"] == "10001"
        mock_request.assert_called_once_with(
            "GET", "https://example.atlassian.net/rest/servicedeskapi/request/10001"
        )


@pytest.mark.asyncio
async def test_get_single_incident(mock_jira_client: JiraClient) -> None:
    """Test getting a single incident by ID."""
    mock_response_data = {
        "id": "incident-1",
        "status": "open",
        "title": "Database issue",
        "description": "Database connection issues",
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ) as mock_request:
        incident = await mock_jira_client.get_single_incident("incident-1")

        assert incident["title"] == "Database issue"
        mock_request.assert_called_once_with(
            "GET",
            "https://example.atlassian.net/rest/api/2/opsgenie/incidents/incident-1",
        )


@pytest.mark.asyncio
async def test_get_single_asset(mock_jira_client: JiraClient) -> None:
    """Test getting a single asset by object ID."""
    mock_response_data = {
        "id": "asset-1",
        "objectType": {"name": "Server"},
        "name": "web-server-01",
        "attributes": [
            {
                "objectTypeAttribute": {"name": "IP"},
                "objectAttributeValues": [{"value": "192.168.1.100"}],
            }
        ],
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ) as mock_request:
        asset = await mock_jira_client.get_single_asset("asset-1")

        assert asset["name"] == "web-server-01"
        mock_request.assert_called_once_with(
            "GET", "https://example.atlassian.net/rest/insight/1.0/object/asset-1"
        )


@pytest.mark.asyncio
async def test_get_single_schedule(mock_jira_client: JiraClient) -> None:
    """Test getting a single schedule by ID."""
    mock_response_data = {
        "id": "schedule-1",
        "name": "On-call Schedule 1",
        "timezone": "UTC",
        "teams": [{"name": "DevOps Team"}],
    }

    with patch.object(
        mock_jira_client, "_send_api_request", return_value=mock_response_data
    ) as mock_request:
        schedule = await mock_jira_client.get_single_schedule("schedule-1")

        assert schedule["name"] == "On-call Schedule 1"
        mock_request.assert_called_once_with(
            "GET",
            "https://example.atlassian.net/rest/api/2/opsgenie/schedules/schedule-1",
        )
