from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.rds.db_cluster.exporter import RdsDbClusterExporter
from aws.core.exporters.rds.db_cluster.models import (
    SingleDbClusterRequest,
    PaginatedDbClusterRequest,
    DbCluster,
    DbClusterProperties,
)


class TestRdsDbClusterExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> RdsDbClusterExporter:
        return RdsDbClusterExporter(mock_session)

    def test_service_name(self, exporter: RdsDbClusterExporter) -> None:
        assert exporter._service_name == "rds"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = RdsDbClusterExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_cluster.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbClusterExporter,
    ) -> None:
        """Test successful retrieval of a single DB cluster."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_db_clusters.return_value = {
            "DBClusters": [
                {
                    "DBClusterIdentifier": "cluster-1",
                    "Engine": "aurora-mysql",
                    "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1",
                }
            ]
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        db_cluster = DbCluster(
            Properties=DbClusterProperties(
                DBClusterIdentifier="cluster-1",
                Engine="aurora-mysql",
                DBClusterArn="arn:aws:rds:us-east-1:123456789012:cluster:cluster-1",
            )
        )
        mock_inspector.inspect.return_value = [db_cluster.dict(exclude_none=True)]

        options = SingleDbClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            db_cluster_identifier="cluster-1",
            include=["ListTagsForResourceAction"],
        )

        result = await exporter.get_resource(options)

        assert result == db_cluster.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "rds")
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once()
        call_args = mock_inspector.inspect.call_args
        assert call_args[0][1] == ["ListTagsForResourceAction"]
        call_kwargs = mock_inspector.inspect.call_args[1]
        assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
        assert call_kwargs["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_cluster.exporter.ResourceInspector")
    async def test_get_resource_returns_empty_when_inspector_returns_nothing(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbClusterExporter,
    ) -> None:
        """Test that an empty dict is returned when the inspector yields no results."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_db_clusters.return_value = {"DBClusters": []}

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = SingleDbClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            db_cluster_identifier="cluster-missing",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_cluster.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbClusterExporter,
    ) -> None:
        """Test that inspector exceptions propagate."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_db_clusters.return_value = {
            "DBClusters": [{"DBClusterIdentifier": "cluster-bad"}]
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("DB cluster not found")

        options = SingleDbClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            db_cluster_identifier="cluster-bad",
            include=[],
        )

        with pytest.raises(Exception, match="DB cluster not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbClusterExporter,
    ) -> None:
        """Test successful retrieval of paginated DB clusters."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {"DBClusterIdentifier": "cluster-1", "Engine": "aurora-mysql"},
                {"DBClusterIdentifier": "cluster-2", "Engine": "aurora-postgresql"},
            ]
            yield [
                {"DBClusterIdentifier": "cluster-3", "Engine": "mysql"},
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        c1 = DbCluster(Properties=DbClusterProperties(DBClusterIdentifier="cluster-1"))
        c2 = DbCluster(Properties=DbClusterProperties(DBClusterIdentifier="cluster-2"))
        c3 = DbCluster(Properties=DbClusterProperties(DBClusterIdentifier="cluster-3"))

        mock_inspector.inspect.side_effect = [
            [c1.dict(exclude_none=True), c2.dict(exclude_none=True)],
            [c3.dict(exclude_none=True)],
        ]

        options = PaginatedDbClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            include=["ListTagsForResourceAction"],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == c1.dict(exclude_none=True)
        assert collected[1] == c2.dict(exclude_none=True)
        assert collected[2] == c3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "rds")
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_db_clusters", "DBClusters"
        )
        assert mock_inspector.inspect.call_count == 2

        for call in mock_inspector.inspect.call_args_list:
            assert call[0][1] == ["ListTagsForResourceAction"]
            assert call[1]["extra_context"]["AccountId"] == "123456789012"
            assert call[1]["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_cluster.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbClusterExporter,
    ) -> None:
        """Test handling of empty paginated results."""
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        options = PaginatedDbClusterRequest(
            region="eu-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_db_clusters", "DBClusters"
        )
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_cluster.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbClusterExporter,
    ) -> None:
        """Test that the async context manager is properly entered and exited."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        mock_client.describe_db_clusters.return_value = {
            "DBClusters": [
                {
                    "DBClusterIdentifier": "cluster-55",
                    "Engine": "aurora-mysql",
                    "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-55",
                }
            ]
        }

        mock_inspector = AsyncMock()
        db_cluster = DbCluster(
            Properties=DbClusterProperties(DBClusterIdentifier="cluster-55")
        )
        mock_inspector.inspect.return_value = [db_cluster.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleDbClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            db_cluster_identifier="cluster-55",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["DBClusterIdentifier"] == "cluster-55"
        assert result["Type"] == "AWS::RDS::DBCluster"

        mock_inspector.inspect.assert_called_once()
        call_kwargs = mock_inspector.inspect.call_args[1]
        assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
        assert call_kwargs["extra_context"]["Region"] == "us-east-1"

        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "rds")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
