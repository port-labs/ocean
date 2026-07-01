from unittest.mock import MagicMock, patch

from aws.utils import Consts
from aws.utils.region_helper import RegionHelper


class TestGetPartition:
    def test_returns_aws_partition_from_config(self) -> None:
        with patch(
            "aws.utils.region_helper.ocean", new_callable=MagicMock
        ) as mock_ocean:
            mock_ocean.integration_config.get.side_effect = lambda key, *args: {
                "aws_partition": "aws-cn"
            }.get(key)

            result = RegionHelper.get_partition()

        assert result == "aws-cn"
        mock_ocean.integration_config.get.assert_called_once_with(
            "aws_partition", Consts.default_partition
        )
