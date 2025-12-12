import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from auth.basic_authenticator import BasicAuthenticator
from auth.oauth_authenticator import OAuthClientCredentialsAuthenticator
from client import ServicenowClient

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
    "state": "2",
    "severity": "3",
    "cvss_score": "7.5",
    "cvss_v3_score": "7.8",
    "first_found": "2024-01-15 10:30:00",
    "last_found": "2024-01-20 14:45:00",
    "due_date": "2024-02-15 00:00:00",
    "assigned_to": {
        "link": "https://test-instance.service-now.com/api/now/table/sys_user/1234567890abcdef1234567890abcdef",
        "value": "1234567890abcdef1234567890abcdef",
        "display_value": "John Doe",
    },
    "assignment_group": {
        "link": "https://test-instance.service-now.com/api/now/table/sys_user_group/9876543210fedcba9876543210fedcba",
        "value": "9876543210fedcba9876543210fedcba",
        "display_value": "Security Operations",
    },
    "priority": "2",
    "risk_score": "85",
    "vulnerability": {
        "link": "https://test-instance.service-now.com/api/now/table/sn_vuln_vulnerability/abcdef1234567890abcdef1234567890",
        "value": "abcdef1234567890abcdef1234567890",
        "display_value": "CVE-2024-12345 - Remote Code Execution",
    },
    "ci_item": {
        "link": "https://test-instance.service-now.com/api/now/table/cmdb_ci_server/11111111111111111111111111111111",
        "value": "11111111111111111111111111111111",
        "display_value": "Production Web Server 01",
    },
    "sys_created_on": "2024-01-15 10:30:00",
    "sys_created_by": "admin",
    "sys_updated_on": "2024-01-20 14:45:00",
    "sys_updated_by": "security.user",
    "active": "true",
}
