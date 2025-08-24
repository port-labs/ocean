import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession

from aws.auth.region_resolver import RegionResolver
from integration import AWSResourceSelector, RegionPolicy


class TestRegionResolver:
    """Test RegionResolver."""

    @pytest.fixture
    def mock_aiosession(self) -> AsyncMock:
        """Create a mock AioSession."""
        return AsyncMock(spec=AioSession)

    @pytest.fixture
    def mock_selector(self) -> MagicMock:
        """Create a mock AWSDescribeResourcesSelector."""
        return MagicMock(spec=AWSResourceSelector)

    @pytest.fixture
    def resolver(
        self, mock_aiosession: AsyncMock, mock_selector: MagicMock
    ) -> RegionResolver:
        """Create a RegionResolver instance."""
        return RegionResolver(
            session=mock_aiosession,
            selector=mock_selector,
            account_id="123456789012",
        )

    def test_initialization_with_account_id(
        self, mock_aiosession: AsyncMock, mock_selector: MagicMock
    ) -> None:
        """Test RegionResolver initialization with account_id."""
        resolver = RegionResolver(
            session=mock_aiosession,
            selector=mock_selector,
            account_id="123456789012",
        )
        assert resolver.session == mock_aiosession
        assert resolver.selector == mock_selector
        assert resolver.account_id == "123456789012"

    @pytest.mark.asyncio
    async def test_get_enabled_regions_success(
        self, resolver: RegionResolver, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_enabled_regions successfully retrieves enabled regions from AWS Account API."""
        # Mock the AWS Account API response
        mock_account_client = AsyncMock()
        mock_account_client.list_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1", "RegionOptStatus": "ENABLED"},
                {"RegionName": "us-west-2", "RegionOptStatus": "ENABLED"},
                {"RegionName": "eu-west-1", "RegionOptStatus": "ENABLED_BY_DEFAULT"},
                {"RegionName": "ap-southeast-1", "RegionOptStatus": "ENABLED"},
            ]
        }

        # Mock the session context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_account_client
        mock_context_manager.__aexit__.return_value = None

        with patch.object(
            mock_aiosession, "create_client", return_value=mock_context_manager
        ):
            regions = await resolver.get_enabled_regions()

            # Verify the correct regions are returned
            assert regions == ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

            # Verify the AWS Account API was called correctly
            mock_aiosession.create_client.assert_called_once_with(
                "account", region_name=None
            )
            mock_account_client.list_regions.assert_called_once_with(
                RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"]
            )

    @pytest.mark.asyncio
    async def test_get_enabled_regions_empty_response(
        self, resolver: RegionResolver, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_enabled_regions handles empty response from AWS Account API."""
        mock_account_client = AsyncMock()
        mock_account_client.list_regions.return_value = {"Regions": []}

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_account_client
        mock_context_manager.__aexit__.return_value = None

        with patch.object(
            mock_aiosession, "create_client", return_value=mock_context_manager
        ):
            regions = await resolver.get_enabled_regions()
            assert regions == []

    @pytest.mark.asyncio
    async def test_get_enabled_regions_client_error(
        self, resolver: RegionResolver, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_enabled_regions handles client creation error."""
        with patch.object(
            mock_aiosession, "create_client", side_effect=Exception("Client error")
        ):
            with pytest.raises(Exception, match="Client error"):
                await resolver.get_enabled_regions()

    @pytest.mark.asyncio
    async def test_get_allowed_regions_with_real_selector(
        self, resolver: RegionResolver, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_allowed_regions with a real AWSDescribeResourcesSelector instance."""
        # Create a real selector with region policy
        region_policy = RegionPolicy(allow=["us-east-1", "us-west-2"])
        real_selector = AWSResourceSelector(query="test", regionPolicy=region_policy)

        # Update resolver with real selector
        resolver.selector = real_selector

        # Mock AWS Account API response
        mock_account_client = AsyncMock()
        mock_account_client.list_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1", "RegionOptStatus": "ENABLED"},
                {"RegionName": "us-west-2", "RegionOptStatus": "ENABLED"},
                {"RegionName": "eu-west-1", "RegionOptStatus": "ENABLED"},
                {"RegionName": "ap-southeast-1", "RegionOptStatus": "ENABLED"},
            ]
        }

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_account_client
        mock_context_manager.__aexit__.return_value = None

        with patch.object(
            mock_aiosession, "create_client", return_value=mock_context_manager
        ):
            regions = await resolver.get_allowed_regions()

            # Only us-east-1 and us-west-2 should be allowed based on the region policy
            assert regions == {"us-east-1", "us-west-2"}
