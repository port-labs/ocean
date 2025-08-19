from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.s3.bucket.exporter import S3BucketExporter
from aws.core.exporters.s3.bucket.models import (
    Bucket,
    BucketProperties,
    SingleBucketRequest,
    PaginatedBucketRequest,
)


class TestS3BucketExporter:

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
    ) -> S3BucketExporter:
        """Create an S3BucketExporter instance for testing."""
        return S3BucketExporter(mock_session, mock_account_id)

    def test_service_name(self, exporter: S3BucketExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "s3"

    def test_initialization(
        self, mock_session: AsyncMock, mock_account_id: str
    ) -> None:
        """Test that the exporter initializes correctly."""
        exporter = S3BucketExporter(mock_session, mock_account_id)
        assert exporter.session == mock_session
        assert exporter.account_id == mock_account_id

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.s3.bucket.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: S3BucketExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create expected Bucket response
        expected_bucket = Bucket(
            Properties=BucketProperties(
                BucketName="test-bucket", Tags=[{"Key": "Environment", "Value": "test"}]
            ),
        )
        mock_inspector.inspect.return_value = expected_bucket

        # Create options
        options = SingleBucketRequest(
            region="us-west-2",
            bucket_name="test-bucket",
            include=["GetBucketTaggingAction"],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        assert result == expected_bucket.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "s3")
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with(
            "test-bucket", ["GetBucketTaggingAction"]
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.s3.bucket.exporter.ResourceInspector")
    async def test_get_resource_with_different_options(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: S3BucketExporter,
    ) -> None:
        """Test single resource retrieval with different configuration options."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        expected_bucket = Bucket(
            Properties=BucketProperties(
                BucketName="prod-bucket",
                BucketEncryption={"Rules": []},
                PublicAccessBlockConfiguration={"BlockPublicAcls": True},
            ),
        )
        mock_inspector.inspect.return_value = expected_bucket

        # Create options with multiple includes
        options = SingleBucketRequest(
            region="eu-west-1",
            bucket_name="prod-bucket",
            include=["GetBucketEncryptionAction", "GetBucketPublicAccessBlockAction"],
        )

        # Execute
        result = await exporter.get_resource(options)

        # Verify
        assert result == expected_bucket.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "eu-west-1", "s3")
        mock_inspector.inspect.assert_called_once_with(
            "prod-bucket",
            ["GetBucketEncryptionAction", "GetBucketPublicAccessBlockAction"],
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.s3.bucket.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: S3BucketExporter,
    ) -> None:
        """Test successful paginated resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator - return the async generator directly
        async def mock_paginate() -> AsyncGenerator[list[dict[str, str]], None]:
            yield [{"Name": "bucket1"}, {"Name": "bucket2"}]
            yield [{"Name": "bucket3"}]

        # Create an object that has a paginate method returning the async generator
        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, str]], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Mock inspector.inspect to return bucket data
        bucket1 = Bucket(Properties=BucketProperties(BucketName="bucket1"))
        bucket2 = Bucket(Properties=BucketProperties(BucketName="bucket2"))
        bucket3 = Bucket(Properties=BucketProperties(BucketName="bucket3"))

        # Set up side effects for inspector.inspect calls
        mock_inspector.inspect.side_effect = [bucket1, bucket2, bucket3]

        # Create options
        options = PaginatedBucketRequest(
            region="us-east-1", include=["GetBucketTaggingAction"]
        )

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify
        assert len(results) == 3
        assert results[0] == bucket1.dict(exclude_none=True)
        assert results[1] == bucket2.dict(exclude_none=True)
        assert results[2] == bucket3.dict(exclude_none=True)

        # Verify mock calls
        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "s3")
        mock_proxy.get_paginator.assert_called_once_with("list_buckets", "Buckets")
        mock_inspector_class.assert_called_once()

        # Verify inspector.inspect was called for each bucket
        assert mock_inspector.inspect.call_count == 3
        mock_inspector.inspect.assert_any_call("bucket1", ["GetBucketTaggingAction"])
        mock_inspector.inspect.assert_any_call("bucket2", ["GetBucketTaggingAction"])
        mock_inspector.inspect.assert_any_call("bucket3", ["GetBucketTaggingAction"])

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.s3.bucket.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty_buckets(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: S3BucketExporter,
    ) -> None:
        """Test paginated resource retrieval with no buckets."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock empty paginator - return the async generator directly
        async def mock_paginate() -> AsyncGenerator[list[dict[str, str]], None]:
            yield []

        # Create an object that has a paginate method returning the async generator
        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, str]], None]:
                return mock_paginate()

        # Make sure get_paginator returns our MockPaginator, not a coroutine
        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Mock inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Create options
        options = PaginatedBucketRequest(region="us-west-2", include=[])

        # Execute and collect results
        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        # Verify
        assert len(results) == 0
        mock_proxy.get_paginator.assert_called_once_with("list_buckets", "Buckets")
        # Inspector should not be called for inspection since no buckets
        assert mock_inspector.inspect.call_count == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.s3.bucket.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: S3BucketExporter,
    ) -> None:
        """Test that exceptions from inspector are properly propagated."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Bucket not found")

        # Create options
        options = SingleBucketRequest(
            region="us-west-2",
            bucket_name="nonexistent-bucket",
            include=["GetBucketTaggingAction"],
        )

        # Execute and verify exception
        with pytest.raises(Exception, match="Bucket not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.s3.bucket.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.s3.bucket.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: S3BucketExporter,
    ) -> None:
        """Test that context manager cleanup is properly handled."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        # Setup inspector to return a normal result
        mock_inspector = AsyncMock()
        mock_bucket = Bucket(
            Properties=BucketProperties(BucketName="test-bucket"),
        )
        mock_inspector.inspect.return_value = mock_bucket
        mock_inspector_class.return_value = mock_inspector

        options = SingleBucketRequest(
            region="us-west-2", bucket_name="test-bucket", include=[]
        )

        # Execute the method
        result = await exporter.get_resource(options)

        # Verify the result is a dictionary with the correct structure
        assert result["Properties"]["BucketName"] == "test-bucket"
        assert result["Type"] == "AWS::S3::Bucket"
        assert result["Properties"]["BucketName"] == "test-bucket"

        # Verify the inspector was called correctly
        mock_inspector.inspect.assert_called_once_with("test-bucket", [])

        # Verify the context manager was used correctly (__aenter__ and __aexit__ were called)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "s3")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
