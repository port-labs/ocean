from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ec2.volume.exporter import EbsVolumeExporter
from aws.core.exporters.ec2.volume.models import (
    SingleEbsVolumeRequest,
    PaginatedEbsVolumeRequest,
    EbsVolume,
    EbsVolumeProperties,
)


class TestEbsVolumeExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EbsVolumeExporter:
        return EbsVolumeExporter(mock_session)

    def test_service_name(self, exporter: EbsVolumeExporter) -> None:
        assert exporter._service_name == "ec2"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = EbsVolumeExporter(mock_session)
        assert exporter.session == mock_session

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.volume.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.volume.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EbsVolumeExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        volume = EbsVolume(
            Properties=EbsVolumeProperties(
                VolumeId="vol-111",
                VolumeType="gp3",
                Size=100,
            )
        )
        mock_inspector.inspect.return_value = [volume.dict(exclude_none=True)]

        mock_client.describe_volumes.return_value = {
            "Volumes": [{"VolumeId": "vol-111", "VolumeType": "gp3", "Size": 100}]
        }

        options = SingleEbsVolumeRequest(
            region="us-east-1",
            account_id="123456789012",
            volume_id="vol-111",
        )

        result = await exporter.get_resource(options)

        assert result == volume.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ec2")
        mock_client.describe_volumes.assert_called_once_with(VolumeIds=["vol-111"])
        mock_inspector.inspect.assert_called_once_with(
            [{"VolumeId": "vol-111", "VolumeType": "gp3", "Size": 100}],
            [],
            extra_context={"AccountId": "123456789012", "Region": "us-east-1"},
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.volume.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.volume.exporter.ResourceInspector")
    async def test_get_resource_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EbsVolumeExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_volumes.return_value = {"Volumes": []}

        options = SingleEbsVolumeRequest(
            region="us-east-1",
            account_id="123456789012",
            volume_id="vol-nonexistent",
        )

        result = await exporter.get_resource(options)
        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.volume.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.volume.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EbsVolumeExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"VolumeId": "vol-111", "VolumeType": "gp3"},
                {"VolumeId": "vol-222", "VolumeType": "io2"},
            ]
            yield [{"VolumeId": "vol-333", "VolumeType": "gp2"}]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        vol1 = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-111"))
        vol2 = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-222"))
        vol3 = EbsVolume(Properties=EbsVolumeProperties(VolumeId="vol-333"))

        mock_inspector.inspect.side_effect = [
            [vol1.dict(exclude_none=True), vol2.dict(exclude_none=True)],
            [vol3.dict(exclude_none=True)],
        ]

        options = PaginatedEbsVolumeRequest(
            region="us-east-1",
            account_id="123456789012",
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == vol1.dict(exclude_none=True)
        assert collected[1] == vol2.dict(exclude_none=True)
        assert collected[2] == vol3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ec2")
        mock_proxy.get_paginator.assert_called_once_with("describe_volumes", "Volumes")
        assert mock_inspector.inspect.call_count == 2

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.volume.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.volume.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EbsVolumeExporter,
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

        options = PaginatedEbsVolumeRequest(
            region="eu-west-1",
            account_id="123456789012",
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with("describe_volumes", "Volumes")
        mock_inspector.inspect.assert_not_called()
