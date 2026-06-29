import pytest
from typing import Generator
from unittest.mock import AsyncMock, patch

from aws.utils.location_utils import LocationUtils


class TestGetAllAvailableRegions:
    @pytest.fixture(autouse=True)
    def reset_cache(self) -> Generator[None, None, None]:
        LocationUtils._available_regions = []
        yield
        LocationUtils._available_regions = []

    @pytest.mark.asyncio
    async def test_returns_regions_from_session(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        regions = ["us-east-1", "us-west-2", "eu-west-1"]
        mock_session.get_available_regions.return_value = regions

        with patch.object(LocationUtils, "get_partition", return_value="aws"):
            # Act
            result = await LocationUtils.get_all_available_regions(mock_session)
            result_from_cache = await LocationUtils.get_all_available_regions(mock_session)

        # Assert
        assert result == regions
        assert result_from_cache == regions
        mock_session.get_available_regions.assert_called_once_with(
            "ec2", partition_name="aws"
        )
