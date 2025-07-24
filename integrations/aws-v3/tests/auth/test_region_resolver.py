import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, AsyncGenerator
from contextlib import asynccontextmanager

from aws.auth.region_resolver import RegionResolver

from tests.conftest import AWS_TEST_ACCOUNT_ID


def create_mock_session_with_client(mock_client: AsyncMock) -> AsyncMock:
    """Helper to create a mock session that returns the given client."""
    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_create_client(*args, **kwargs) -> AsyncGenerator[Any, None]:
        yield mock_client

    mock_session.create_client = mock_create_client
    return mock_session


class TestRegionResolver:
    """Test RegionResolver functionality."""

    def test_initialization_with_required_parameters(self) -> None:
        """Test RegionResolver initializes with required parameters."""
        mock_session = AsyncMock()
        mock_selector = MagicMock()
        resolver = RegionResolver(
            session=mock_session, selector=mock_selector, account_id=AWS_TEST_ACCOUNT_ID
        )
        assert resolver.session == mock_session
        assert resolver.selector == mock_selector
        assert resolver.account_id == AWS_TEST_ACCOUNT_ID

    def test_initialization_without_account_id(self) -> None:
        """Test RegionResolver initializes without account_id."""
        mock_session = AsyncMock()
        mock_selector = MagicMock()
        resolver = RegionResolver(session=mock_session, selector=mock_selector)
        assert resolver.session == mock_session
        assert resolver.selector == mock_selector
        assert resolver.account_id is None

    @pytest.mark.asyncio
    async def test_get_enabled_regions_parses_response_correctly(
        self, mock_session_with_account_client: Any
    ) -> None:
        """Test that get_enabled_regions correctly parses the response."""
        mock_selector = MagicMock()

        resolver = RegionResolver(mock_session_with_account_client, mock_selector)
        regions = await resolver.get_enabled_regions()

        assert "us-east-1" in regions
        assert "eu-west-1" in regions
        assert "us-west-2" in regions
        assert len(regions) == 3

    @pytest.mark.asyncio
    async def test_get_enabled_regions_handles_empty_response(self) -> None:
        """Test that get_enabled_regions handles empty response correctly."""
        mock_selector = MagicMock()

        mock_client = AsyncMock()
        mock_client.list_regions.return_value = {"Regions": []}

        mock_session = create_mock_session_with_client(mock_client)

        resolver = RegionResolver(mock_session, mock_selector)
        regions = await resolver.get_enabled_regions()

        assert regions == []

    @pytest.mark.asyncio
    async def test_get_enabled_regions_handles_missing_regions_key(self) -> None:
        """Test that get_enabled_regions handles missing 'Regions' key correctly."""
        mock_selector = MagicMock()

        mock_client = AsyncMock()
        mock_client.list_regions.return_value = {}

        mock_session = create_mock_session_with_client(mock_client)

        resolver = RegionResolver(mock_session, mock_selector)
        regions = await resolver.get_enabled_regions()

        assert regions == []

    @pytest.mark.asyncio
    async def test_get_enabled_regions_handles_session_creation_error(self) -> None:
        """Test that get_enabled_regions handles session creation errors."""
        mock_session = AsyncMock()
        mock_selector = MagicMock()

        def mock_create_client_raises(*args, **kwargs):
            raise Exception("Session creation failed")

        mock_session.create_client = mock_create_client_raises

        resolver = RegionResolver(mock_session, mock_selector)

        with pytest.raises(Exception, match="Session creation failed"):
            await resolver.get_enabled_regions()

    @pytest.mark.asyncio
    async def test_get_enabled_regions_handles_client_error(self) -> None:
        """Test that get_enabled_regions handles client creation errors."""
        mock_session = AsyncMock()
        mock_selector = MagicMock()

        def mock_create_client_raises(*args, **kwargs):
            raise Exception("Client creation failed")

        mock_session.create_client = mock_create_client_raises

        resolver = RegionResolver(mock_session, mock_selector)

        with pytest.raises(Exception, match="Client creation failed"):
            await resolver.get_enabled_regions()

    @pytest.mark.asyncio
    async def test_get_enabled_regions_handles_list_regions_error(self) -> None:
        """Test that get_enabled_regions handles list_regions API errors."""
        mock_selector = MagicMock()

        mock_client = AsyncMock()
        mock_client.list_regions.side_effect = Exception("API error")

        mock_session = create_mock_session_with_client(mock_client)

        resolver = RegionResolver(mock_session, mock_selector)

        with pytest.raises(Exception, match="API error"):
            await resolver.get_enabled_regions()

    @pytest.mark.asyncio
    async def test_get_allowed_regions_uses_selector(
        self, mock_session_with_account_client: Any
    ) -> None:
        """Test that get_allowed_regions uses the selector to filter regions."""
        mock_selector = MagicMock()

        mock_selector.is_region_allowed.side_effect = lambda region: region in [
            "us-east-1",
            "eu-west-1",
        ]

        resolver = RegionResolver(mock_session_with_account_client, mock_selector)
        allowed_regions = await resolver.get_allowed_regions()

        assert "us-east-1" in allowed_regions
        assert "eu-west-1" in allowed_regions
        assert "us-west-2" not in allowed_regions
        assert len(allowed_regions) == 2

        assert mock_selector.is_region_allowed.call_count == 3

    @pytest.mark.asyncio
    async def test_get_allowed_regions_handles_empty_enabled_regions(self) -> None:
        """Test that get_allowed_regions handles empty enabled regions."""
        mock_selector = MagicMock()

        mock_client = AsyncMock()
        mock_client.list_regions.return_value = {"Regions": []}

        mock_session = create_mock_session_with_client(mock_client)

        resolver = RegionResolver(mock_session, mock_selector)
        allowed_regions = await resolver.get_allowed_regions()

        assert allowed_regions == set()
        mock_selector.is_region_allowed.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_allowed_regions_handles_selector_error(
        self, mock_session_with_account_client: Any
    ) -> None:
        """Test that get_allowed_regions handles selector errors."""
        mock_selector = MagicMock()

        mock_selector.is_region_allowed.side_effect = Exception("Selector error")

        resolver = RegionResolver(mock_session_with_account_client, mock_selector)

        with pytest.raises(Exception, match="Selector error"):
            await resolver.get_allowed_regions()
