import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from auth.basic_authenticator import BasicAuthenticator
from auth.oauth_authenticator import OAuthClientCredentialsAuthenticator
from client import ServicenowClient
from webhook.webhook_client import ServicenowWebhookClient
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "servicenow_url": "https://test-instance.service-now.com",
    "servicenow_username": "test_user",
    "servicenow_password": "test_password",
    "servicenow_client_id": "test_client_id",
    "servicenow_client_secret": "test_client_secret",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_ocean_app.config.client_timeout = 30.0
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://app.example.com"
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def basic_authenticator() -> BasicAuthenticator:
    """Create a basic authenticator fixture."""
    return BasicAuthenticator(
        username=TEST_INTEGRATION_CONFIG["servicenow_username"],
        password=TEST_INTEGRATION_CONFIG["servicenow_password"],
    )


@pytest.fixture
def oauth_authenticator() -> OAuthClientCredentialsAuthenticator:
    """Create an OAuth authenticator fixture."""
    return OAuthClientCredentialsAuthenticator(
        servicenow_url=TEST_INTEGRATION_CONFIG["servicenow_url"],
        client_id=TEST_INTEGRATION_CONFIG["servicenow_client_id"],
        client_secret=TEST_INTEGRATION_CONFIG["servicenow_client_secret"],
    )


@pytest.fixture
def servicenow_client(basic_authenticator: BasicAuthenticator) -> ServicenowClient:
    """Create a ServiceNow client fixture with basic auth."""
    return ServicenowClient(
        servicenow_url=TEST_INTEGRATION_CONFIG["servicenow_url"],
        authenticator=basic_authenticator,
    )


@pytest.fixture
def servicenow_client_oauth(
    oauth_authenticator: OAuthClientCredentialsAuthenticator,
) -> ServicenowClient:
    """Create a ServiceNow client fixture with OAuth."""
    return ServicenowClient(
        servicenow_url=TEST_INTEGRATION_CONFIG["servicenow_url"],
        authenticator=oauth_authenticator,
    )


# Sample test data
SAMPLE_USER_DATA = {
    "sys_id": "1234567890abcdef1234567890abcdef",
    "user_name": "test.user",
    "first_name": "Test",
    "last_name": "User",
    "email": "test.user@example.com",
    "active": "true",
    "sys_created_on": "2024-01-15 10:30:00",
    "sys_created_by": "admin",
}

SAMPLE_INCIDENT_DATA = {
    "sys_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "number": "INC0010001",
    "short_description": "Test Incident",
    "state": "2",
    "severity": "3",
    "priority": "2",
    "urgency": "2",
    "category": "network",
    "active": "true",
    "sys_created_on": "2024-01-15 10:30:00",
    "sys_created_by": "admin",
}

SAMPLE_VULNERABILITY_DATA = {
    "sys_id": "v1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "number": "VIT0010001",
    "state": "2",
    "cmdb_ci": "test123",
    "priority": "2",
    "risk_score": "85",
    "first_found": "2024-01-15",
    "last_found": "2024-01-20",
    "sys_created_on": "2024-01-15 10:30:00",
    "sys_created_by": "admin",
    "sys_updated_on": "2024-01-20 14:45:00",
    "sys_updated_by": "security.user",
    "active": "true",
}

SAMPLE_RELEASE_PROJECT_DATA = {
    "sys_id": "r1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "number": "REL0010001",
    "name": "Test Release Project",
    "state": "2",
    "priority": "2",
    "active": "true",
    "sys_created_on": "2024-01-15 10:30:00",
    "sys_created_by": "admin",
}

SAMPLE_SC_CATALOG_DATA = {
    "sys_id": "c1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "title": "Test SC Catalog",
    "active": "true",
    "sys_created_on": "2024-01-15 10:30:00",
    "sys_created_by": "admin",
}

SAMPLE_USER_GROUP_DATA = {
    "sys_id": "g1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "name": "Test User Group",
    "roles": "test123",
    "manager": {
        "sys_id": "test123",
        "name": "test123",
    },
    "active": "true",
    "sys_created_on": "2024-01-15 10:30:00",
    "sys_created_by": "admin",
}


@pytest.fixture
def webhook_client(basic_authenticator: BasicAuthenticator) -> ServicenowWebhookClient:
    """Create a ServiceNow webhook client fixture with basic auth."""
    return ServicenowWebhookClient(
        servicenow_url=TEST_INTEGRATION_CONFIG["servicenow_url"],
        authenticator=basic_authenticator,
    )


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    """Create a mock WebhookEvent fixture."""
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
