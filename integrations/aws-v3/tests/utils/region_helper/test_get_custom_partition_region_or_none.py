import pytest
from unittest.mock import AsyncMock, patch

from aws.utils.region_helper import RegionHelper
from aws.utils.consts import Consts


class TestGetCustomPartitionRegionOrNone:
    @pytest.mark.asyncio
    async def test_returns_none_for_default_partition(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        with (
            patch.object(
                RegionHelper, "get_partition", return_value=Consts.default_partition
            ),
            patch.object(
                RegionHelper,
                "get_first_available_region",
                new_callable=AsyncMock,
            ) as mock_get_first,
        ):
            # Act
            result = await RegionHelper.get_custom_partition_region_or_none(
                mock_session
            )

        # Assert
        assert result is None
        mock_get_first.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_first_region_for_non_default_partition(self) -> None:
        # Arrange
        mock_session = AsyncMock()
        with (
            patch.object(RegionHelper, "get_partition", return_value="aws-us-gov"),
            patch.object(
                RegionHelper,
                "get_first_available_region",
                new_callable=AsyncMock,
                return_value="us-gov-west-1",
            ) as mock_get_region,
        ):
            # Act
            result = await RegionHelper.get_custom_partition_region_or_none(
                mock_session
            )

        # Assert
        assert result == "us-gov-west-1"
        mock_get_region.asscalled_once_with(mock_session)
