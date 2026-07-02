import pytest
from typing import Generator
from unittest.mock import MagicMock, patch, call

from aws.utils.region_helper import RegionHelper
from aws.utils.consts import Consts


class TestGetPartition:
    @pytest.fixture(autouse=True)
    def reset_cache(self) -> Generator[None, None, None]:
        RegionHelper._partition = ""
        yield
        RegionHelper._partition = ""

    def test_returns_aws_partition_from_config(self) -> None:
        with patch(
            "aws.utils.region_helper.ocean", new_callable=MagicMock
        ) as mock_ocean:
            mock_ocean.integration_config.get.side_effect = lambda key: {
                "aws_partition": "aws-cn"
            }.get(key)

            result = RegionHelper.get_partition()

        assert result == "aws-cn"
        mock_ocean.integration_config.get.assert_has_calls(
            [call("aws_partition"), call("aws_partition")]
        )

    def test_returns_partition_from_role_arn(self) -> None:
        with patch(
            "aws.utils.region_helper.ocean", new_callable=MagicMock
        ) as mock_ocean:
            mock_ocean.integration_config.get.side_effect = lambda key: {
                "accountRoleArn": "arn:aws-us-gov:iam::123456789012:role/test-role"
            }.get(key)
            result = RegionHelper.get_partition()

        assert result == "aws-us-gov"
        mock_ocean.integration_config.get.assert_has_calls(
            [call("aws_partition"), call("accountRoleArn"), call("accountRoleArn")]
        )

    def test_returns_default_partition_when_no_config(self) -> None:
        with patch(
            "aws.utils.region_helper.ocean", new_callable=MagicMock
        ) as mock_ocean:
            mock_ocean.integration_config.get.side_effect = lambda key: {}.get(key)
            result = RegionHelper.get_partition()

        assert result == Consts.default_partition
        mock_ocean.integration_config.get.assert_has_calls(
            [call("aws_partition"), call("accountRoleArn")]
        )

    def test_aws_partition_takes_precedence_over_role_arn(self) -> None:
        with patch(
            "aws.utils.region_helper.ocean", new_callable=MagicMock
        ) as mock_ocean:
            mock_ocean.integration_config.get.side_effect = lambda key: {
                "aws_partition": "aws-cn",
                "accountRoleArn": "arn:aws-us-gov:iam::123456789012:role/test-role",
            }.get(key)

            result = RegionHelper.get_partition()

        assert result == "aws-cn"
        mock_ocean.integration_config.get.assert_has_calls(
            [call("aws_partition"), call("aws_partition")]
        )

    def test_cache_prevents_second_config_read(self) -> None:
        with patch(
            "aws.utils.region_helper.ocean", new_callable=MagicMock
        ) as mock_ocean:
            RegionHelper._partition = "aws-cn"
            result = RegionHelper.get_partition()

        assert result == "aws-cn"
        mock_ocean.integration_config.get.assert_not_called()
