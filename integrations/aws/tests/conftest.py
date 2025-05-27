import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Generator

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from aws.session_manager import SessionManager

MOCK_ORG_URL: str = "https://mock-organization-url.com"
MOCK_PERSONAL_ACCESS_TOKEN: str = "mock-personal_access_token"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""
    try:
        mock_ocean_app: MagicMock = MagicMock()
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
    """Mock the event context."""
    mock_event: MagicMock = MagicMock(spec=EventContext)

    with patch("port_ocean.context.event.event_context", mock_event):
        yield mock_event


@pytest.fixture
def mock_session() -> AsyncMock:
    """Creates a mocked session with a client factory and credentials."""
    mock_session: AsyncMock = AsyncMock()
    mock_session.region_name = "us-west-2"

    @asynccontextmanager
    async def mock_client(
        service_name: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        if service_name == "cloudformation":

            class MockCloudFormationClient:
                async def describe_method(self, **kwargs: Any) -> Dict[str, Any]:
                    return {
                        "NextToken": None,
                        "ResourceList": [
                            {
                                "Properties": {"Name": "test-resource"},
                                "Identifier": "test-id",
                            }
                        ],
                    }

            yield MockCloudFormationClient()
        elif service_name == "cloudcontrol":

            class MockCloudControlClient:
                async def list_resources(self, **kwargs: Any) -> Dict[str, Any]:
                    return {
                        "NextToken": None,
                        "ResourceDescriptions": [
                            {
                                "Properties": json.dumps({"Name": "test-resource"}),
                                "Identifier": "test-id",
                            }
                        ],
                    }

                async def get_resource(self, **kwargs: Any) -> Dict[str, Any]:
                    return {
                        "ResourceDescription": {
                            "Properties": json.dumps({"Name": "test-resource"}),
                            "Identifier": "test-id",
                        },
                        "TypeName": "string",
                    }

                def get_paginator(self, method_name: str) -> Any:
                    class AsyncPaginatorMock:
                        async def paginate(
                            self, **kwargs: Any
                        ) -> AsyncGenerator[Dict[str, Any], None]:
                            yield {
                                "ResourceDescriptions": [
                                    {
                                        "Properties": json.dumps(
                                            {"Name": "test-resource"}
                                        ),
                                        "Identifier": "test-id",
                                    }
                                ]
                            }

                    return AsyncPaginatorMock()

            yield MockCloudControlClient()
        elif service_name == "resource-groups":

            class MockResourceGroupsClient:
                def get_paginator(self, method_name: str) -> Any:
                    class AsyncPaginatorMock:
                        async def paginate(
                            self, **kwargs: Any
                        ) -> AsyncGenerator[Dict[str, Any], None]:
                            yield {
                                "Groups": [
                                    {
                                        "GroupName": "test-group",
                                        "GroupArn": "test-group-arn",
                                    }
                                ]
                            }

                    return AsyncPaginatorMock()

            yield MockResourceGroupsClient()
        else:
            raise NotImplementedError(f"Client for service '{service_name}' not mocked")

    # Provide a mock for get_credentials
    class MockFrozenCredentials:
        access_key: str = "mock_access_key"
        secret_key: str = "mock_secret_key"
        token: str = "mock_session_token"

    class MockCredentials:
        async def get_frozen_credentials(self) -> MockFrozenCredentials:
            return MockFrozenCredentials()

    mock_session.get_credentials.return_value = MockCredentials()
    mock_session.client = mock_client
    return mock_session


@pytest.fixture
def mock_account_id() -> str:
    """Mocks the account ID."""
    return "123456789012"


@pytest.fixture
def mock_resource_config() -> MagicMock:
    """Mocks the resource config."""
    mock_resource_config: MagicMock = MagicMock()
    mock_resource_config.selector.is_region_allowed.return_value = True
    return mock_resource_config


@pytest.fixture(autouse=True)
def mock_application_creds_patch() -> Generator[None, None, None]:
    """
    Patch SessionManager._get_application_credentials and
    SessionManager._update_available_access_credentials with side_effect
    to prevent actual calls.
    """

    def mock_get_application_credentials() -> "MockApplicationCredentials":
        return MockApplicationCredentials()

    def mock_update_available_access_credentials() -> None:
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

            def __init__(self, region_name: str = "us-west-2"):
                self.region_name: str = region_name

            @asynccontextmanager
            async def client(
                self, service_name: str, **kwargs: Any
            ) -> AsyncGenerator[AsyncMock, None]:
                if service_name == "sts":
                    mock_client: AsyncMock = AsyncMock()
                    mock_client.get_caller_identity.return_value = {
                        "Account": "123456789012"
                    }
                    yield mock_client
                else:
                    yield AsyncMock()

        class MockApplicationCredentials:
            """Simulates the object that your SessionManager code expects."""

            def __init__(self, *args: Any, **kwargs: Any):
                self.aws_access_key_id: str = "mock_access_key_id"
                self.aws_secret_access_key: str = "mock_secret_access_key"
                self.region_name: str = "us-west-2"
                self.account_id: str = "123456789012"

            async def create_session(
                self, *args: Any, **kwargs: Any
            ) -> MockAioboto3Session:
                """
                Return an object that looks like an aioboto3.Session,
                i.e. has .client(...) that returns an async context manager
                for services like 'sts' and 'organizations'.
                """
                return MockAioboto3Session()

        yield
