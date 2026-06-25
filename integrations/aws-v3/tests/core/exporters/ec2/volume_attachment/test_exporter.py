from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ec2.volume_attachment.exporter import EC2VolumeAttachmentExporter
from aws.core.exporters.ec2.volume_attachment.models import (
    SingleEC2VolumeAttachmentRequest,
    PaginatedEC2VolumeAttachmentRequest,
    EC2VolumeAttachment,
    EC2VolumeAttachmentProperties,
)


class TestEC2VolumeAttachmentExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EC2VolumeAttachmentExporter:
        return EC2VolumeAttachmentExporter(mock_session)

    def test_service_name(self, exporter: EC2VolumeAttachmentExporter) -> None:
        assert exporter._service_name == "ec2"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = EC2VolumeAttachmentExporter(mock_session)
        assert exporter.session == mock_session

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.ResourceInspector"
    )
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2VolumeAttachmentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        attachment = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-111",
                InstanceId="i-abc123",
                Device="/dev/sda1",
                State="attached",
            )
        )
        mock_inspector.inspect.return_value = [attachment.dict(exclude_none=True)]

        options = SingleEC2VolumeAttachmentRequest(
            region="us-east-1",
            account_id="123456789012",
            volume_id="vol-111",
        )

        result = await exporter.get_resource(options)

        assert result == attachment.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ec2")
        mock_inspector.inspect.assert_called_once_with(
            [{"VolumeId": "vol-111"}],
            [],
            extra_context={"AccountId": "123456789012", "Region": "us-east-1"},
        )

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.ResourceInspector"
    )
    async def test_get_resource_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2VolumeAttachmentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = SingleEC2VolumeAttachmentRequest(
            region="us-east-1",
            account_id="123456789012",
            volume_id="vol-nonexistent",
        )

        result = await exporter.get_resource(options)
        assert result == {}

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.ResourceInspector"
    )
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2VolumeAttachmentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "VolumeId": "vol-111",
                    "Attachments": [{"InstanceId": "i-abc", "State": "attached"}],
                },
                {
                    "VolumeId": "vol-222",
                    "Attachments": [{"InstanceId": "i-def", "State": "attached"}],
                },
            ]
            yield [
                {
                    "VolumeId": "vol-333",
                    "Attachments": [{"InstanceId": "i-ghi", "State": "attaching"}],
                }
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        att1 = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-111", InstanceId="i-abc"
            )
        )
        att2 = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-222", InstanceId="i-def"
            )
        )
        att3 = EC2VolumeAttachment(
            Properties=EC2VolumeAttachmentProperties(
                VolumeId="vol-333", InstanceId="i-ghi"
            )
        )

        mock_inspector.inspect.side_effect = [
            [att1.dict(exclude_none=True), att2.dict(exclude_none=True)],
            [att3.dict(exclude_none=True)],
        ]

        options = PaginatedEC2VolumeAttachmentRequest(
            region="us-east-1",
            account_id="123456789012",
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == att1.dict(exclude_none=True)
        assert collected[1] == att2.dict(exclude_none=True)
        assert collected[2] == att3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ec2")
        mock_proxy.get_paginator.assert_called_once_with("describe_volumes", "Volumes")
        assert mock_inspector.inspect.call_count == 2

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.ResourceInspector"
    )
    async def test_get_paginated_resources_skips_unattached_volumes(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2VolumeAttachmentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            # Only unattached volumes (no attachments)
            yield [
                {"VolumeId": "vol-111", "Attachments": []},
                {"VolumeId": "vol-222"},  # no Attachments key
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        options = PaginatedEC2VolumeAttachmentRequest(
            region="eu-west-1",
            account_id="123456789012",
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with("describe_volumes", "Volumes")
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ec2.volume_attachment.exporter.ResourceInspector"
    )
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2VolumeAttachmentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        options = PaginatedEC2VolumeAttachmentRequest(
            region="eu-west-1",
            account_id="123456789012",
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with("describe_volumes", "Volumes")
        mock_inspector.inspect.assert_not_called()
