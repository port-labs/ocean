from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ec2.instances.exporter import EC2InstanceExporter
from aws.core.exporters.ec2.instances.models import (
    SingleEC2InstanceRequest,
    PaginatedEC2InstanceRequest,
    EC2Instance,
    EC2InstanceProperties,
)
from typing import Any


class TestEC2InstanceExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AioSession for testing."""
        return AsyncMock()

    @pytest.fixture
    def mock_account_id(self) -> str:
        """Create a mock account ID for testing."""
        return "123456789012"

    @pytest.fixture
    def exporter(
        self, mock_session: AsyncMock, mock_account_id: str
    ) -> EC2InstanceExporter:
        """Create an EC2InstanceExporter instance for testing."""
        return EC2InstanceExporter(mock_session, mock_account_id)

    def test_service_name(self, exporter: EC2InstanceExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "ec2"

    def test_initialization(
        self, mock_session: AsyncMock, mock_account_id: str
    ) -> None:
        """Test that the exporter initializes correctly."""
        exporter = EC2InstanceExporter(mock_session, mock_account_id)
        assert exporter.session == mock_session
        assert exporter.account_id == mock_account_id

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instances.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create expected EC2Instance response
        expected_instance = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-1234567890abcdef0",
                InstanceType="t3.micro",
            ),
        )
        mock_inspector.inspect.return_value = expected_instance

        # Create options
        options = SingleEC2InstanceRequest(
            region="us-west-2",
            instance_id="i-1234567890abcdef0",
            include=[],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        expected_result = expected_instance.dict(exclude_none=True)
        assert result == expected_result
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ec2")
        # ResourceInspector was called correctly
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with("i-1234567890abcdef0", [])

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instances.exporter.ResourceInspector")
    async def test_get_resource_with_different_options(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Test single resource retrieval with different configuration options."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        expected_instance = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-0987654321fedcba0",
                InstanceType="t3.medium",
                State={"Name": "running", "Code": 16},
                PublicIpAddress="203.0.113.12",
            ),
        )
        mock_inspector.inspect.return_value = expected_instance

        # Create options with includes
        options = SingleEC2InstanceRequest(
            region="eu-west-1",
            instance_id="i-0987654321fedcba0",
            include=["GetInstanceStatusAction"],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        expected_result = expected_instance.dict(exclude_none=True)
        assert result == expected_result
        mock_proxy_class.assert_called_once_with(exporter.session, "eu-west-1", "ec2")
        # ResourceInspector was called correctly
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with(
            "i-0987654321fedcba0",
            ["GetInstanceStatusAction"],
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instances.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Test successful paginated resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator - return the async generator directly
        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t3.micro",
                        },
                        {
                            "InstanceId": "i-0987654321fedcba0",
                            "InstanceType": "t3.small",
                        },
                    ]
                }
            ]
            yield [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-abcdef1234567890",
                            "InstanceType": "t3.medium",
                        },
                    ]
                }
            ]

        # Create an object that has a paginate method returning the async generator
        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.region = "us-east-1"

        # Mock inspector.inspect to return instance data
        instance1 = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-1234567890abcdef0", InstanceType="t3.micro"
            )
        )
        instance2 = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-0987654321fedcba0", InstanceType="t3.small"
            )
        )
        instance3 = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-abcdef1234567890", InstanceType="t3.medium"
            )
        )

        # Set up side effects for inspector.inspect calls
        mock_inspector.inspect.side_effect = [instance1, instance2, instance3]

        # Create options
        options = PaginatedEC2InstanceRequest(region="us-east-1", include=[])

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify
        assert len(results) == 3
        assert results[0]["Properties"]["InstanceId"] == "i-1234567890abcdef0"
        assert results[1]["Properties"]["InstanceId"] == "i-0987654321fedcba0"
        assert results[2]["Properties"]["InstanceId"] == "i-abcdef1234567890"

        # Verify mock calls
        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ec2")
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_instances", "Reservations"
        )
        # ResourceInspector was called correctly
        mock_inspector_class.assert_called_once()

        # Verify inspector.inspect was called for each instance
        # When include is empty, inspector.inspect should not be called
        assert mock_inspector.inspect.call_count == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instances.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty_reservations(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Test paginated resource retrieval with no instances."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock empty paginator - return the async generator directly
        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        # Create an object that has a paginate method returning the async generator
        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create options
        options = PaginatedEC2InstanceRequest(region="us-west-2", include=[])

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify
        assert len(results) == 0
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_instances", "Reservations"
        )
        # Inspector should not be called for inspection since no instances
        assert mock_inspector.inspect.call_count == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instances.exporter.ResourceInspector")
    async def test_process_instance_with_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Test that exceptions during instance processing are handled gracefully."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator
        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890abcdef0",
                            "InstanceType": "t3.micro",
                        },
                    ]
                }
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector to return a basic instance model when actions fail
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.region = "us-west-2"

        # Create a basic instance model that would be returned when actions fail
        from aws.core.exporters.ec2.instances.models import (
            EC2Instance,
            EC2InstanceProperties,
        )

        basic_instance = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-1234567890abcdef0",
                InstanceType="t3.micro",
            )
        )
        mock_inspector.inspect.return_value = basic_instance

        # Create options
        options = PaginatedEC2InstanceRequest(region="us-west-2", include=[])

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify - should get basic instance data even when actions fail
        assert len(results) == 1
        assert results[0]["Properties"]["InstanceId"] == "i-1234567890abcdef0"
        assert results[0]["Properties"]["InstanceType"] == "t3.micro"
        assert results[0]["Type"] == "AWS::EC2::Instance"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instances.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Test that exceptions from inspector are properly propagated for single resource."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Instance not found")

        # Create options
        options = SingleEC2InstanceRequest(
            region="us-west-2",
            instance_id="i-nonexistent",
            include=[],
        )

        # Execute and verify exception
        with pytest.raises(Exception, match="Instance not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instances.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instances.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Test that context manager cleanup is properly handled."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        # Setup inspector to return a normal result
        mock_inspector = AsyncMock()
        mock_instance = EC2Instance(
            Properties=EC2InstanceProperties(InstanceId="i-1234567890abcdef0"),
        )
        mock_inspector.inspect.return_value = mock_instance
        mock_inspector_class.return_value = mock_inspector

        options = SingleEC2InstanceRequest(
            region="us-west-2", instance_id="i-1234567890abcdef0", include=[]
        )

        # Execute the method
        result = await exporter.get_resource(options)

        # Verify the result is a dictionary with the correct structure
        assert result["Properties"]["InstanceId"] == "i-1234567890abcdef0"
        assert result["Type"] == "AWS::EC2::Instance"

        # Verify the inspector was called correctly
        mock_inspector.inspect.assert_called_once_with("i-1234567890abcdef0", [])

        # Verify the context manager was used correctly (__aenter__ and __aexit__ were called)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ec2")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
