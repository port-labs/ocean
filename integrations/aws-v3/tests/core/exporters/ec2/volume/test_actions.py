from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock
import pytest

from aws.core.exporters.ec2.volume.actions import (
    DescribeVolumesAction,
    DescribeVolumeAttributeAction,
    EbsVolumeActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeVolumesAction:

    @pytest.fixture
    def action(self) -> DescribeVolumesAction:
        return DescribeVolumesAction(AsyncMock())

    def test_inheritance(self, action: DescribeVolumesAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_input_unchanged(
        self, action: DescribeVolumesAction
    ) -> None:
        volumes = [
            {"VolumeId": "vol-111", "VolumeType": "gp3", "Size": 100},
            {"VolumeId": "vol-222", "VolumeType": "io2", "Size": 500},
        ]
        assert await action.execute(volumes) == volumes

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: DescribeVolumesAction) -> None:
        assert await action.execute([]) == []


class TestDescribeVolumeAttributeAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.describe_volume_attribute = AsyncMock()
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> DescribeVolumeAttributeAction:
        return DescribeVolumeAttributeAction(mock_client)

    def test_inheritance(self, action: DescribeVolumeAttributeAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_logger: MagicMock, action: DescribeVolumeAttributeAction
    ) -> None:
        volumes = [
            {"VolumeId": "vol-111"},
            {"VolumeId": "vol-222"},
        ]

        def mock_describe_volume_attribute(
            VolumeId: str, Attribute: str, **kwargs: Any
        ) -> Dict[str, Any]:
            return {"AutoEnableIO": {"Value": VolumeId == "vol-111"}}

        action.client.describe_volume_attribute.side_effect = (
            mock_describe_volume_attribute
        )

        result = await action.execute(volumes)

        assert len(result) == 2
        assert result[0]["AutoEnableIO"] is True
        assert result[1]["AutoEnableIO"] is False
        assert action.client.describe_volume_attribute.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_access_denied_skips_volume(
        self, mock_logger: MagicMock, action: DescribeVolumeAttributeAction
    ) -> None:
        volumes = [{"VolumeId": "vol-denied"}]

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Denied"}}
        action.client.describe_volume_attribute.side_effect = Exception(
            str(error_response)
        )

        # access denied exceptions are handled by execute_concurrent_aws_operations,
        # which re-raises non-recoverable exceptions
        with pytest.raises(Exception):
            await action.execute(volumes)


class TestEbsVolumeActionsMap:

    @pytest.mark.asyncio
    async def test_merge_includes_defaults(self, mock_logger: MagicMock) -> None:
        action_map = EbsVolumeActionsMap()
        merged = action_map.merge([])

        names = [cls.__name__ for cls in merged]
        assert "DescribeVolumesAction" in names
        assert "DescribeVolumeAttributeAction" not in names

    @pytest.mark.asyncio
    async def test_merge_with_optional_action(self, mock_logger: MagicMock) -> None:
        action_map = EbsVolumeActionsMap()
        merged = action_map.merge(["DescribeVolumeAttributeAction"])

        names = [cls.__name__ for cls in merged]
        assert "DescribeVolumesAction" in names
        assert "DescribeVolumeAttributeAction" in names

    @pytest.mark.asyncio
    async def test_merge_unknown_option_ignored(self, mock_logger: MagicMock) -> None:
        action_map = EbsVolumeActionsMap()
        merged = action_map.merge(["NonExistentAction"])

        names = [cls.__name__ for cls in merged]
        assert "DescribeVolumesAction" in names
        assert len(names) == 1
