from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.rds.db_instance.exporter import RdsDbInstanceExporter
from aws.core.exporters.rds.db_instance.models import (
    SingleDbInstanceRequest,
    PaginatedDbInstanceRequest,
    DbInstance,
    DbInstanceProperties,
)


class TestRdsDbInstanceExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> RdsDbInstanceExporter:
        return RdsDbInstanceExporter(mock_session)

    def test_service_name(self, exporter: RdsDbInstanceExporter) -> None:
        assert exporter._service_name == "rds"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = RdsDbInstanceExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_instance.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbInstanceExporter,
    ) -> None:
        """Test successful retrieval of a single DB instance."""
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock the describe_db_instances call to return proper response
        mock_client.describe_db_instances.return_value = {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "db-1",
                    "DBInstanceClass": "db.t3.micro",
                    "Engine": "mysql",
                    "DBInstanceArn": "arn:aws:rds:us-west-2:123456789012:db:db-1",
                }
            ]
        }

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        db_instance = DbInstance(
            Properties=DbInstanceProperties(
                DBInstanceIdentifier="db-1",
                DBInstanceClass="db.t3.micro",
                Engine="mysql",
            )
        )
        mock_inspector.inspect.return_value = [db_instance.dict(exclude_none=True)]

        options = SingleDbInstanceRequest(
            region="us-west-2",
            account_id="123456789012",
            db_instance_identifier="db-1",
            include=["ListTagsForResourceAction"],
        )

        result = await exporter.get_resource(options)

        assert result == db_instance.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "rds")
        mock_inspector_class.assert_called_once()
        # The actual call will be with the mock client result, not the string directly
        mock_inspector.inspect.assert_called_once()
        call_args = mock_inspector.inspect.call_args
        assert call_args[0][1] == [
            "ListTagsForResourceAction"
        ]  # Second argument should be the include list

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_instance.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbInstanceExporter,
    ) -> None:
        """Test handling of inspector exceptions."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client

        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock the describe_db_instances call to return proper response
        mock_client.describe_db_instances.return_value = {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "db-notexists",
                    "DBInstanceClass": "db.t3.micro",
                    "Engine": "mysql",
                    "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-notexists",
                }
            ]
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("DB instance not found")

        options = SingleDbInstanceRequest(
            region="us-east-1",
            account_id="123456789012",
            db_instance_identifier="db-notexists",
            include=[],
        )

        with pytest.raises(Exception, match="DB instance not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_instance.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbInstanceExporter,
    ) -> None:
        """Test successful retrieval of paginated DB instances."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "db-1",
                            "DBInstanceClass": "db.t3.micro",
                            "Engine": "mysql",
                        },
                        {
                            "DBInstanceIdentifier": "db-2",
                            "DBInstanceClass": "db.t3.small",
                            "Engine": "postgres",
                        },
                    ]
                }
            ]
            yield [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "db-3",
                            "DBInstanceClass": "db.t3.medium",
                            "Engine": "oracle-ee",
                        },
                    ]
                }
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        db1 = DbInstance(Properties=DbInstanceProperties(DBInstanceIdentifier="db-1"))
        db2 = DbInstance(Properties=DbInstanceProperties(DBInstanceIdentifier="db-2"))
        db3 = DbInstance(Properties=DbInstanceProperties(DBInstanceIdentifier="db-3"))

        mock_inspector.inspect.side_effect = [
            [db1.dict(exclude_none=True), db2.dict(exclude_none=True)],
            [db3.dict(exclude_none=True)],
        ]

        options = PaginatedDbInstanceRequest(
            region="us-east-1",
            account_id="123456789012",
            include=["ListTagsForResourceAction"],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == db1.dict(exclude_none=True)
        assert collected[1] == db2.dict(exclude_none=True)
        assert collected[2] == db3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "rds")
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_db_instances", "DBInstances"
        )
        assert mock_inspector.inspect.call_count == 2

        # Verify the calls were made with the correct include list and extra context
        calls = mock_inspector.inspect.call_args_list
        for call in calls:
            call_args = call[0]
            call_kwargs = call[1]
            assert call_args[1] == [
                "ListTagsForResourceAction"
            ]  # Second argument should be the include list
            assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
            assert call_kwargs["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_instance.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbInstanceExporter,
    ) -> None:
        """Test handling of empty paginated results."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = PaginatedDbInstanceRequest(
            region="us-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_db_instances", "DBInstances"
        )
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.rds.db_instance.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: RdsDbInstanceExporter,
    ) -> None:
        """Test that context manager properly cleans up resources."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        # Mock the describe_db_instances call to return proper response
        mock_client.describe_db_instances.return_value = {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "db-55",
                    "DBInstanceClass": "db.t3.micro",
                    "Engine": "mysql",
                    "DBInstanceArn": "arn:aws:rds:us-west-2:123456789012:db:db-55",
                }
            ]
        }

        mock_inspector = AsyncMock()
        db_instance = DbInstance(
            Properties=DbInstanceProperties(DBInstanceIdentifier="db-55")
        )
        mock_inspector.inspect.return_value = [db_instance.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleDbInstanceRequest(
            region="us-west-2",
            account_id="123456789012",
            db_instance_identifier="db-55",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["DBInstanceIdentifier"] == "db-55"
        assert result["Type"] == "AWS::RDS::DBInstance"

        # The actual call will be with the mock client result, not the string directly
        mock_inspector.inspect.assert_called_once()
        call_args = mock_inspector.inspect.call_args
        assert call_args[0][1] == []  # Second argument should be the include list
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "rds")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
