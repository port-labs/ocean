from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.codepipeline.pipeline.exporter import PipelineExporter
from aws.core.exporters.codepipeline.pipeline.models import (
    SinglePipelineRequest,
    PaginatedPipelineRequest,
    Pipeline,
    PipelineProperties,
)


class TestPipelineExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AioSession for testing."""
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> PipelineExporter:
        """Create a PipelineExporter instance for testing."""
        return PipelineExporter(mock_session)

    def test_service_name(self, exporter: PipelineExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "codepipeline"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        """Test that the exporter initializes correctly."""
        exporter = PipelineExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: PipelineExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        pipeline = Pipeline(
            Properties=PipelineProperties(
                Name="test-pipeline",
                RoleArn="arn:aws:iam::123456789012:role/test-pipeline-role",
                PipelineType="V2",
                Version=1,
            )
        )
        mock_inspector.inspect.return_value = [pipeline.dict(exclude_none=True)]

        options = SinglePipelineRequest(
            region="us-east-1",
            account_id="123456789012",
            pipeline_name="test-pipeline",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == pipeline.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "codepipeline"
        )
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once()

        # Verify identifiers passed to inspect contain the pipeline name
        call_args = mock_inspector.inspect.call_args
        identifiers = call_args[0][0]
        assert identifiers == [{"name": "test-pipeline"}]
        assert call_args[0][1] == []

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.ResourceInspector")
    async def test_get_resource_empty_response(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: PipelineExporter,
    ) -> None:
        """Test that an empty inspector response yields an empty dict."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = SinglePipelineRequest(
            region="us-east-1",
            account_id="123456789012",
            pipeline_name="missing-pipeline",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == {}
        mock_inspector.inspect.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: PipelineExporter,
    ) -> None:
        """Test successful retrieval of paginated CodePipeline pipelines."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {"name": "pipeline-1", "version": 1},
                {"name": "pipeline-2", "version": 1},
            ]
            yield [
                {"name": "pipeline-3", "version": 2},
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        pipeline1 = Pipeline(Properties=PipelineProperties(Name="pipeline-1"))
        pipeline2 = Pipeline(Properties=PipelineProperties(Name="pipeline-2"))
        pipeline3 = Pipeline(Properties=PipelineProperties(Name="pipeline-3"))

        mock_inspector.inspect.side_effect = [
            [pipeline1.dict(exclude_none=True), pipeline2.dict(exclude_none=True)],
            [pipeline3.dict(exclude_none=True)],
        ]

        options = PaginatedPipelineRequest(
            region="us-east-1",
            account_id="123456789012",
            include=[],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == pipeline1.dict(exclude_none=True)
        assert collected[1] == pipeline2.dict(exclude_none=True)
        assert collected[2] == pipeline3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "codepipeline"
        )
        mock_proxy.get_paginator.assert_called_once_with("list_pipelines", "pipelines")
        assert mock_inspector.inspect.call_count == 2

        # Verify the calls were made with the correct extra context
        calls = mock_inspector.inspect.call_args_list
        for call in calls:
            call_kwargs = call[1]
            assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
            assert call_kwargs["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: PipelineExporter,
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

        options = PaginatedPipelineRequest(
            region="us-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with("list_pipelines", "pipelines")
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codepipeline.pipeline.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: PipelineExporter,
    ) -> None:
        """Test that context manager properly cleans up resources."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        mock_inspector = AsyncMock()
        pipeline = Pipeline(Properties=PipelineProperties(Name="cleanup-test"))
        mock_inspector.inspect.return_value = [pipeline.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SinglePipelineRequest(
            region="us-west-2",
            account_id="123456789012",
            pipeline_name="cleanup-test",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["Name"] == "cleanup-test"
        assert result["Type"] == "AWS::CodePipeline::Pipeline"

        mock_inspector.inspect.assert_called_once()

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-west-2", "codepipeline"
        )
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
