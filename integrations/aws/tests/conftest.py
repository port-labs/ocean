import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from contextlib import asynccontextmanager

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from aws.session_manager import SessionManager

MOCK_ORG_URL = "https://mock-organization-url.com"
MOCK_PERSONAL_ACCESS_TOKEN = "mock-personal_access_token"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": MOCK_PERSONAL_ACCESS_TOKEN,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> MagicMock:
    """Mock the event context."""
    mock_event = MagicMock(spec=EventContext)

    with patch("port_ocean.context.event.event_context", mock_event):
        yield mock_event


@pytest.fixture
def mock_session():
    """Creates a mocked session with a client factory and credentials."""
    mock_session = AsyncMock()
    mock_session.region_name = "us-west-2"

    @asynccontextmanager
    async def mock_client(service_name, **kwargs):
        if service_name == "s3":

            class MockS3Client:
                async def describe_method(self, **kwargs):
                    return {
                        "NextToken": None,
                        "ResourceList": [
                            {
                                "Properties": {"Name": "test-resource"},
                                "Identifier": "test-id",
                            }
                        ],
                    }

            yield MockS3Client()
        elif service_name == "cloudcontrol":

            class MockCloudControlClient:
                async def list_resources(self, **kwargs):
                    return {
                        "NextToken": None,
                        "ResourceDescriptions": [
                            {
                                "Properties": json.dumps({"Name": "test-resource"}),
                                "Identifier": "test-id",
                            }
                        ],
                    }

            yield MockCloudControlClient()

        else:
            raise NotImplementedError(f"Client for service '{service_name}' not mocked")

    # Provide a mock for get_credentials
    class MockFrozenCredentials:
        access_key = "mock_access_key"
        secret_key = "mock_secret_key"
        token = "mock_session_token"

    class MockCredentials:
        async def get_frozen_credentials(self):
            return MockFrozenCredentials()

    mock_session.get_credentials.return_value = MockCredentials()
    mock_session.client = mock_client
    return mock_session


@pytest.fixture
def mock_account_id():
    """Mocks the account ID."""
    return "123456789012"


@pytest.fixture
def mock_resource_config():
    """Mocks the resource config."""
    mock_resource_config = MagicMock()
    mock_resource_config.selector.is_region_allowed.return_value = True

    return mock_resource_config


@pytest.fixture(autouse=True)
def mock_application_creds_patch():
    """
    Patch SessionManager._get_application_credentials and
    SessionManager._update_available_access_credentials with side_effect
    to prevent actual calls.
    """

    def mock_get_application_credentials():
        return MockApplicationCredentials()

    def mock_update_available_access_credentials():
        pass

    with (
        patch.object(
            SessionManager,
            "_get_application_credentials",
            side_effect=mock_get_application_credentials,
        ),
        patch.object(
            SessionManager,
            "_update_available_access_credentials",
            side_effect=mock_update_available_access_credentials,
        ),
    ):

        class MockAioboto3Session:
            """A fake session object that supports async with for .client(...) calls."""

            def __init__(self, region_name="us-west-2"):  # Set a default region
                self.region_name = region_name

            @asynccontextmanager
            async def client(self, service_name: str, **kwargs):
                if service_name == "sts":
                    mock_client = AsyncMock()
                    mock_client.get_caller_identity.return_value = {
                        "Account": "123456789012"
                    }
                    yield mock_client
                else:
                    yield AsyncMock()

        class MockApplicationCredentials:
            """Simulates the object that your SessionManager code expects."""

            def __init__(self, *args, **kwargs):
                self.aws_access_key_id = "mock_access_key_id"
                self.aws_secret_access_key = "mock_secret_access_key"
                self.region_name = "us-west-2"
                self.account_id = "123456789012"

            async def create_session(self, *args, **kwargs):
                """
                Return an object that looks like an aioboto3.Session,
                i.e. has .client(...) that returns an async context manager
                for services like 'sts' and 'organizations'.
                """
                return MockAioboto3Session()

        yield
