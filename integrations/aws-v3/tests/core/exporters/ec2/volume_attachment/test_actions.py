from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ec2.volume_attachment.actions import (
    DescribeVolumeAttachmentsAction,
    EC2VolumeAttachmentActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeVolumeAttachmentsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.describe_volumes = AsyncMock()
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> DescribeVolumeAttachmentsAction:
        return DescribeVolumeAttachmentsAction(mock_client)

    def test_inheritance(self, action: DescribeVolumeAttachmentsAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        mock_logger: MagicMock,
        action: DescribeVolumeAttachmentsAction,
    ) -> None:
        volumes = [{"VolumeId": "vol-111"}]

        action.client.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-111",
                    "Attachments": [
                        {
                            "InstanceId": "i-abc123",
                            "Device": "/dev/sda1",
                            "State": "attached",
                            "AttachTime": "2024-04-17T20:10:00+00:00",
                            "DeleteOnTermination": True,
                        }
                    ],
                }
            ]
        }

        result = await action.execute(volumes)

        assert len(result) == 1
        assert result[0]["VolumeId"] == "vol-111"
        assert result[0]["InstanceId"] == "i-abc123"
        assert result[0]["Device"] == "/dev/sda1"
        assert result[0]["State"] == "attached"
        assert result[0]["DeleteOnTermination"] is True

    @pytest.mark.asyncio
    async def test_execute_no_attachments(
        self,
        mock_logger: MagicMock,
        action: DescribeVolumeAttachmentsAction,
    ) -> None:
        volumes = [{"VolumeId": "vol-111"}]

        action.client.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-111",
                    "Attachments": [],
                }
            ]
        }

        result = await action.execute(volumes)

        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_empty_list(
        self,
        mock_logger: MagicMock,
        action: DescribeVolumeAttachmentsAction,
    ) -> None:
        result = await action.execute([])
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_access_denied_skips_volume(
        self,
        mock_logger: MagicMock,
        action: DescribeVolumeAttachmentsAction,
    ) -> None:
        volumes = [{"VolumeId": "vol-denied"}]

        error = ClientError(
            error_response={"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            operation_name="DescribeVolumes",
        )
        action.client.describe_volumes.side_effect = error

        result = await action.execute(volumes)

        # Recoverable error must still produce an entry to preserve index alignment
        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_non_recoverable_exception_raises(
        self,
        mock_logger: MagicMock,
        action: DescribeVolumeAttachmentsAction,
    ) -> None:
        volumes = [{"VolumeId": "vol-111"}]

        error = ClientError(
            error_response={
                "Error": {"Code": "InternalError", "Message": "Server error"}
            },
            operation_name="DescribeVolumes",
        )
        action.client.describe_volumes.side_effect = error

        with pytest.raises(ClientError):
            await action.execute(volumes)

    @pytest.mark.asyncio
    async def test_execute_multiple_volumes(
        self,
        mock_logger: MagicMock,
        action: DescribeVolumeAttachmentsAction,
    ) -> None:
        volumes = [{"VolumeId": "vol-111"}, {"VolumeId": "vol-222"}]

        def mock_describe_volumes(VolumeIds: Any, **kwargs: Any) -> Any:
            volume_id = VolumeIds[0]
            if volume_id == "vol-111":
                return {
                    "Volumes": [
                        {
                            "VolumeId": "vol-111",
                            "Attachments": [
                                {
                                    "InstanceId": "i-abc",
                                    "Device": "/dev/sda1",
                                    "State": "attached",
                                    "AttachTime": "2024-04-17T20:10:00+00:00",
                                    "DeleteOnTermination": True,
                                }
                            ],
                        }
                    ]
                }
            else:
                return {
                    "Volumes": [
                        {
                            "VolumeId": "vol-222",
                            "Attachments": [
                                {
                                    "InstanceId": "i-def",
                                    "Device": "/dev/xvdb",
                                    "State": "attached",
                                    "AttachTime": "2024-05-01T10:00:00+00:00",
                                    "DeleteOnTermination": False,
                                }
                            ],
                        }
                    ]
                }

        action.client.describe_volumes.side_effect = mock_describe_volumes

        result = await action.execute(volumes)

        assert len(result) == 2
        assert result[0]["VolumeId"] == "vol-111"
        assert result[0]["InstanceId"] == "i-abc"
        assert result[1]["VolumeId"] == "vol-222"
        assert result[1]["InstanceId"] == "i-def"


class TestEC2VolumeAttachmentActionsMap:

    def test_merge_includes_defaults(self, mock_logger: MagicMock) -> None:
        action_map = EC2VolumeAttachmentActionsMap()
        merged = action_map.merge([])

        names = [cls.__name__ for cls in merged]
        assert "DescribeVolumeAttachmentsAction" in names

    def test_no_optional_actions(self, mock_logger: MagicMock) -> None:
        action_map = EC2VolumeAttachmentActionsMap()
        assert action_map.options == []

    def test_merge_unknown_option_ignored(self, mock_logger: MagicMock) -> None:
        action_map = EC2VolumeAttachmentActionsMap()
        merged = action_map.merge(["NonExistentAction"])

        names = [cls.__name__ for cls in merged]
        assert "DescribeVolumeAttachmentsAction" in names
        assert len(names) == 1
