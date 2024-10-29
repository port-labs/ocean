import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, Dict, Generator
from snyk.client import SnykClient
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext

from port_ocean.tests.helpers.fixtures import (
    get_mocked_ocean_app,
    get_mock_ocean_resource_configs,
)
from port_ocean.tests.helpers.ocean_app import (
    get_raw_result_on_integration_sync_resource_config,
)

MOCK_API_URL = "https://api.snyk.io/v1"
MOCK_TOKEN = "dummy_token"
MOCK_ORG_ID = "org123"
MOCK_USER_ID = "user123"
MOCK_USER_REFERENCE = f"/rest/orgs/{MOCK_ORG_ID}/users/{MOCK_USER_ID}"
MOCK_USER_DETAILS = {"data": {"id": MOCK_USER_ID, "name": "Test User", "email": "testuser@example.com"}}
MOCK_ORG_URL = "https://your_organization_url.com"
MOCK_PERSONAL_ACCESS_TOKEN = "personal_access_token"

SNYK_OCEAN_INTEGRATION_CONFIG = {"organization_id": MOCK_ORG_ID, "token": MOCK_TOKEN}
@pytest.fixture
def snyk_client() -> SnykClient:
    """Fixture to create a SnykClient instance for testing."""
    return SnykClient(
        token=MOCK_TOKEN,
        api_url=MOCK_API_URL,
        app_host=None,
        organization_ids=[MOCK_ORG_ID],  # Set up the organization IDs for testing
        group_ids=None,
        webhook_secret=None,
    )


@pytest.mark.asyncio
async def test_get_user_details(snyk_client: SnykClient, get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any) -> None:
    """Test getting user details with a mocked response."""

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()


    async def mock_send_api_request(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Mock API request method to return user details."""
        url = kwargs.get("url")
        if url == f"{MOCK_API_URL}{MOCK_USER_REFERENCE}":
            return MOCK_USER_DETAILS
        return {}

    with patch.object(
        snyk_client, "_send_api_request", side_effect=mock_send_api_request
    ):
        # Test for existing user details
        user_details = await snyk_client._get_user_details(MOCK_USER_REFERENCE)
        assert user_details == {"id": MOCK_USER_ID, "name": "Test User", "email": "testuser@example.com"}

        # Test for nonexistent user
        user_details_not_found = await snyk_client._get_user_details("/rest/orgs/nonexistent_org/users/nonexistent_user")
        assert user_details_not_found == {}

        # Test for no user reference provided
        user_details_no_reference = await snyk_client._get_user_details(None)
        assert user_details_no_reference == {}

        # Test for organization ID mismatch
        snyk_client.organization_ids = ["other_org_id"]
        user_details_mismatch = await snyk_client._get_user_details(MOCK_USER_REFERENCE)
        assert user_details_mismatch == {}


@patch(
    "port_ocean.context.ocean.PortOceanContext.integration_config",
    return_value={"search_all_resources_per_minute_quota": 100},
)
async def test_get_single_subscription(
    integration_config: Any, monkeypatch: Any
) -> None:
    # Arrange
    subscriber_async_client_mock = AsyncMock
    monkeypatch.setattr(
        "google.pubsub_v1.services.subscriber.SubscriberAsyncClient",
        subscriber_async_client_mock,
    )
    subscriber_async_client_mock.get_subscription = AsyncMock()
    subscriber_async_client_mock.get_subscription.return_value = pubsub.Subscription(
        {"name": "subscription_name"}
    )

    from gcp_core.search.resource_searches import get_single_subscription

    expected_subscription = {
        "ack_deadline_seconds": 0,
        "detached": False,
        "enable_exactly_once_delivery": False,
        "enable_message_ordering": False,
        "filter": "",
        "labels": {},
        "name": "subscription_name",
        "retain_acked_messages": False,
        "state": 0,
        "topic": "",
    }
    mock_project = "project_name"

    # Act
    actual_subscription = await get_single_subscription(
        mock_project, "subscription_name"
    )

    # Assert
    assert actual_subscription == expected_subscription

