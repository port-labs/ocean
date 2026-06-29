import pytest
from unittest.mock import AsyncMock, patch

from aws.utils.location_utils import LocationUtils


class TestGetFirstAvailableRegion:
    @pytest.mark.asyncio
    async def test_returns_first_region_from_list(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        regions = ["us-east-1", "us-west-2", "eu-west-1"]

        with patch.object(
            LocationUtils,
            "get_all_available_regions",
            new_callable=AsyncMock,
            return_value=regions,
        ) as mock_get:
            # Act
            result = await LocationUtils.get_first_available_region(mock_session)

        # Assert
        assert result == "us-east-1"
        mock_get.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_regions(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        with patch.object(
            LocationUtils,
            "get_all_available_regions",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            # Act
            result = await LocationUtils.get_first_available_region(mock_session)

        # Assert
        assert result is None
        mock_get.assert_called_once_with(mock_session)
