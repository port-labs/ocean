from unittest.mock import AsyncMock
import pytest

from aws.core.exporters.codepipeline.action.exporter import CodePipelineActionExporter
from aws.core.exporters.codepipeline.action.models import (
    SingleCodePipelineActionRequest,
    PaginatedCodePipelineActionRequest,
    CodePipelineAction,
)
from aws.core.interfaces.exporter import IResourceExporter


class TestCodePipelineActionExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AWS session."""
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> CodePipelineActionExporter:
        """Create a CodePipelineActionExporter instance for testing."""
        return CodePipelineActionExporter(mock_session)

    def test_inheritance(self, exporter: CodePipelineActionExporter) -> None:
        """Test that the exporter inherits from IResourceExporter."""
        assert isinstance(exporter, IResourceExporter)

    def test_service_name(self, exporter: CodePipelineActionExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "codepipeline"

    def test_model_cls(self, exporter: CodePipelineActionExporter) -> None:
        """Test that the model class is correctly set."""
        assert exporter._model_cls == CodePipelineAction

    @pytest.mark.asyncio
    async def test_get_resource_success(
        self, exporter: CodePipelineActionExporter
    ) -> None:
        """Test successful single resource retrieval."""
        # Mock the options
        options = SingleCodePipelineActionRequest(
            region="us-east-1",
            account_id="123456789012",
            pipeline_name="test-pipeline",
            stage_name="Source",
            action_name="SourceAction",
        )

        # Mock the response data
        mock_action_data = {
            "Type": "AWS::CodePipeline::Action",
            "Properties": {
                "ActionName": "SourceAction",
                "StageName": "Source",
                "PipelineName": "test-pipeline",
                "ActionTypeId": {
                    "Category": "Source",
                    "Owner": "AWS",
                    "Provider": "S3",
                    "Version": "1",
                },
            },
        }

        # Mock the AioBaseClientProxy and ResourceInspector
        with (
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.AioBaseClientProxy"
            ) as mock_proxy,
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.ResourceInspector"
            ) as mock_inspector,
        ):
            # Configure the mocks
            mock_proxy.return_value.__aenter__ = AsyncMock()
            mock_proxy.return_value.__aexit__ = AsyncMock()

            mock_inspector_instance = AsyncMock()
            mock_inspector_instance.inspect.return_value = [mock_action_data]
            mock_inspector.return_value = mock_inspector_instance

            # Execute the method
            result = await exporter.get_resource(options)

            # Verify the result
            assert result == mock_action_data

    @pytest.mark.asyncio
    async def test_get_resource_not_found(
        self, exporter: CodePipelineActionExporter
    ) -> None:
        """Test single resource retrieval when action is not found."""
        options = SingleCodePipelineActionRequest(
            region="us-east-1",
            account_id="123456789012",
            pipeline_name="test-pipeline",
            stage_name="Source",
            action_name="NonExistentAction",
        )

        # Mock empty response
        with (
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.AioBaseClientProxy"
            ) as mock_proxy,
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.ResourceInspector"
            ) as mock_inspector,
        ):
            # Configure the mocks
            mock_proxy.return_value.__aenter__ = AsyncMock()
            mock_proxy.return_value.__aexit__ = AsyncMock()

            mock_inspector_instance = AsyncMock()
            mock_inspector_instance.inspect.return_value = []
            mock_inspector.return_value = mock_inspector_instance

            # Execute the method
            result = await exporter.get_resource(options)

            # Verify empty result
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_paginated_resources_success(
        self, exporter: CodePipelineActionExporter
    ) -> None:
        """Test successful paginated resource retrieval."""
        options = PaginatedCodePipelineActionRequest(
            region="us-east-1", account_id="123456789012"
        )

        mock_actions_batch = [
            {
                "Type": "AWS::CodePipeline::Action",
                "Properties": {
                    "ActionName": "SourceAction",
                    "StageName": "Source",
                    "PipelineName": "test-pipeline-1",
                },
            },
            {
                "Type": "AWS::CodePipeline::Action",
                "Properties": {
                    "ActionName": "BuildAction",
                    "StageName": "Build",
                    "PipelineName": "test-pipeline-1",
                },
            },
        ]

        with (
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.AioBaseClientProxy"
            ) as mock_proxy,
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.ResourceInspector"
            ) as mock_inspector,
        ):
            # Configure the mocks
            mock_proxy_instance = AsyncMock()
            mock_proxy_instance.__aenter__ = AsyncMock(return_value=mock_proxy_instance)
            mock_proxy_instance.__aexit__ = AsyncMock()

            # Mock paginator
            mock_paginator = AsyncMock()
            mock_paginator.paginate.return_value.__aiter__ = AsyncMock(
                return_value=iter(
                    [[{"name": "test-pipeline-1"}, {"name": "test-pipeline-2"}]]
                )
            )
            mock_proxy_instance.get_paginator.return_value = mock_paginator
            mock_proxy.return_value = mock_proxy_instance

            # Mock inspector
            mock_inspector_instance = AsyncMock()
            mock_inspector_instance.inspect.return_value = mock_actions_batch
            mock_inspector.return_value = mock_inspector_instance

            # Execute the method
            results = []
            async for batch in exporter.get_paginated_resources(options):
                results.extend(batch)

            # Verify the results
            assert len(results) == 2
            assert results[0]["Properties"]["ActionName"] == "SourceAction"
            assert results[1]["Properties"]["ActionName"] == "BuildAction"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty(
        self, exporter: CodePipelineActionExporter
    ) -> None:
        """Test paginated resource retrieval with no pipelines."""
        options = PaginatedCodePipelineActionRequest(
            region="us-east-1", account_id="123456789012"
        )

        with (
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.AioBaseClientProxy"
            ) as mock_proxy,
            pytest.mock.patch(
                "aws.core.exporters.codepipeline.action.exporter.ResourceInspector"
            ) as mock_inspector,
        ):
            # Configure the mocks for empty result
            mock_proxy_instance = AsyncMock()
            mock_proxy_instance.__aenter__ = AsyncMock(return_value=mock_proxy_instance)
            mock_proxy_instance.__aexit__ = AsyncMock()

            mock_paginator = AsyncMock()
            mock_paginator.paginate.return_value.__aiter__ = AsyncMock(
                return_value=iter([[]])
            )
            mock_proxy_instance.get_paginator.return_value = mock_paginator
            mock_proxy.return_value = mock_proxy_instance

            # Execute the method
            results = []
            async for batch in exporter.get_paginated_resources(options):
                results.extend(batch)

            # Verify empty results
            assert len(results) == 0
