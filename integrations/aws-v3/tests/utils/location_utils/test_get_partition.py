import pytest
from typing import Generator
from unittest.mock import MagicMock, patch

from aws.utils.location_utils import LocationUtils


class TestGetPartition:
    @pytest.fixture(autouse=True)
    def reset_cache(self) -> Generator[None, None, None]:
        LocationUtils._partition = ""
        yield
        LocationUtils._partition = ""

    def test_returns_aws_partition_from_config(self) -> None:
        with patch(
            "aws.utils.location_utils.ocean", new_callable=MagicMock
        ) as mock_ocean:
            mock_ocean.integration_config.get.side_effect = lambda key: {
                "aws_partition": "aws-cn"
            }.get(key)

            result = LocationUtils.get_partition()

        assert result == "aws-cn"
        mock_ocean.integration_config.get.assert_called_once_with("aws_partition")
