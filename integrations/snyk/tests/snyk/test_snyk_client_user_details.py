import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from typing import Dict, Any, Optional
from port_ocean.context.event import event
from port_ocean.context.event import event_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.ocean import initialize_port_ocean_context
from snyk.client import SnykClient
from aiolimiter import AsyncLimiter


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app: MagicMock = MagicMock()
        mock_ocean_app.config.integration.config: dict[str, str] = {
            "organization_url": "https://test.com",
            "token": "test-token",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


class TestSnykClientUserDetails:
    @pytest.fixture
    def snyk_client(self) -> SnykClient:
        """Create a SnykClient instance with test configuration"""
        with patch("port_ocean.utils.http_async_client"):
            client: SnykClient = SnykClient(
                token="test-token",
                api_url="https://api.test.com",
                app_host=None,
                organization_ids=["org123"],
                group_ids=None,
                webhook_secret=None,
                rate_limiter=AsyncLimiter(5, 1),
            )
            client._send_api_request = AsyncMock()
            return client

    @pytest.fixture
    def mock_event_context(self) -> MagicMock:
        """Create a mock event context for tests"""
        mock_event: MagicMock = MagicMock()
        mock_event.attributes = {}

        with patch("port_ocean.context.event.event", mock_event):
            yield mock_event

    @pytest.mark.asyncio
    async def test_none_user_reference(
        self, snyk_client: SnykClient, mock_event_context: MagicMock
    ) -> None:
        """Test handling of None user reference"""
        async with event_context("test_event"):
            result: Dict[str, Any] = await snyk_client._get_user_details(None)
            assert result == {}
            snyk_client._send_api_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_from_different_org(
        self, snyk_client: SnykClient, mock_event_context: MagicMock
    ) -> None:
        """Test handling of user from non-configured organization"""
        async with event_context("test_event"):
            # Arrange
            user_reference: str = "/rest/orgs/different_org/users/user123"

            # Act
            result: Dict[str, Any] = await snyk_client._get_user_details(user_reference)

            # Assert
            assert result == {}
            snyk_client._send_api_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_cached_user_details(
        self, snyk_client: SnykClient, mock_event_context: MagicMock
    ) -> None:
        """Test retrieval of cached user details"""
        async with event_context("test_event"):
            # Arrange
            user_id: str = "user123"
            user_reference: str = f"/rest/orgs/org123/users/{user_id}"
            cached_data: Dict[str, Any] = {"data": {"id": user_id, "name": "Test User"}}
            event.attributes[f"user-{user_id}"] = cached_data

            # Act
            result: Dict[str, Any] = await snyk_client._get_user_details(user_reference)

            # Assert
            assert result == cached_data
            snyk_client._send_api_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_user_details_fetch(
        self, snyk_client: SnykClient, mock_event_context: MagicMock
    ) -> None:
        async with event_context("test_event"):
            # Arrange
            user_id: str = "user123"
            user_reference: str = f"/rest/orgs/org123/users/{user_id}"
            api_response: Dict[str, Any] = {
                "data": {"id": user_id, "name": "Test User"}
            }

            # Use return_value directly instead of creating a task
            snyk_client._send_api_request.return_value = api_response

            # Act
            result: Dict[str, Any] = await snyk_client._get_user_details(user_reference)

            # Assert
            assert result == api_response["data"]
            snyk_client._send_api_request.assert_called_once_with(
                url=f"https://api.test.com/rest/orgs/org123/users/{user_id}",
                query_params={"version": "2024-06-21~beta"},
            )
            assert event.attributes[f"user-{user_id}"] == api_response

    @pytest.mark.asyncio
    async def test_404_error_handling(
        self, snyk_client: SnykClient, mock_event_context: MagicMock
    ) -> None:
        async with event_context("test_event"):
            # Arrange
            user_reference: str = "/rest/orgs/org123/users/user123"
            mock_response: MagicMock = MagicMock(spec=httpx.Response)
            mock_response.status_code = 404
            error: httpx.HTTPStatusError = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(spec=httpx.Request),
                response=mock_response,
            )

            async def mock_raise_error(
                url: str, query_params: Optional[Dict[str, str]] = None
            ) -> None:
                raise error

            snyk_client._send_api_request.side_effect = mock_raise_error

            # Act
            result: Dict[str, Any] = await snyk_client._get_user_details(user_reference)

            # Assert
            assert result == {}

    @pytest.mark.asyncio
    async def test_non_404_error_handling(
        self, snyk_client: SnykClient, mock_event_context: MagicMock
    ) -> None:
        async with event_context("test_event"):
            # Arrange
            user_reference: str = "/rest/orgs/org123/users/user123"
            mock_response: MagicMock = MagicMock(spec=httpx.Response)
            mock_response.status_code = 500
            error: httpx.HTTPStatusError = httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(spec=httpx.Request),
                response=mock_response,
            )

            async def mock_raise_error(
                url: str, query_params: Optional[Dict[str, str]] = None
            ) -> None:
                raise error

            snyk_client._send_api_request.side_effect = mock_raise_error

            # Act/Assert
            with pytest.raises(httpx.HTTPStatusError):
                await snyk_client._get_user_details(user_reference)

    @pytest.mark.asyncio
    async def test_empty_api_response(
        self, snyk_client: SnykClient, mock_event_context: MagicMock
    ) -> None:
        async with event_context("test_event"):
            # Arrange
            user_reference: str = "/rest/orgs/org123/users/user123"

            snyk_client._send_api_request.return_value = None

            # Act
            result: Dict[str, Any] = await snyk_client._get_user_details(user_reference)

            # Assert
            assert result == {}
