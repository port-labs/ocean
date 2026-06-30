from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from aws.core.exporters.codepipeline.pipeline_execution.exporter import (
    CodePipelinePipelineExecutionExporter,
)
from aws.core.exporters.codepipeline.pipeline_execution.models import (
    SinglePipelineExecutionRequest,
    PaginatedPipelineExecutionRequest,
)

patch_prefix = "aws.core.exporters.codepipeline.pipeline_execution.exporter"


@pytest.fixture
def single_options() -> SinglePipelineExecutionRequest:
    return SinglePipelineExecutionRequest(
        region="us-east-1",
        account_id="123456789012",
        pipeline_name="test-pipeline",
        pipeline_execution_id="execution-1",
        include=[],
    )


@pytest.fixture
def paginated_options() -> PaginatedPipelineExecutionRequest:
    return PaginatedPipelineExecutionRequest(
        region="us-east-1",
        account_id="123456789012",
        include=[],
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelineExecutionActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    single_options: SinglePipelineExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelinePipelineExecutionExporter(AsyncMock())
    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    mock_response = MagicMock()
    mock_inspector.inspect.return_value = [mock_response]

    # Act
    result = await exporter.get_resource(single_options)

    # Assert
    assert result == mock_response
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_options.region, "codepipeline"
    )
    mock_input.assert_called_once_with(
        items=[
            {
                "pipelineName": single_options.pipeline_name,
                "pipelineExecutionId": single_options.pipeline_execution_id,
            }
        ],
        pipeline_name=single_options.pipeline_name,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value,
        single_options.include,
        extra_context={
            "AccountId": single_options.account_id,
            "Region": single_options.region,
        },
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelineExecutionActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_empty_response(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    single_options: SinglePipelineExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelinePipelineExecutionExporter(AsyncMock())
    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector
    mock_inspector.inspect.return_value = []

    # Act
    result = await exporter.get_resource(single_options)

    # Assert
    assert result == {}
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_options.region, "codepipeline"
    )
    mock_input.assert_called_once_with(
        items=[
            {
                "pipelineName": single_options.pipeline_name,
                "pipelineExecutionId": single_options.pipeline_execution_id,
            }
        ],
        pipeline_name=single_options.pipeline_name,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value,
        single_options.include,
        extra_context={
            "AccountId": single_options.account_id,
            "Region": single_options.region,
        },
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelineExecutionActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    paginated_options: PaginatedPipelineExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelinePipelineExecutionExporter(AsyncMock())
    mock_proxy = AsyncMock()
    mock_proxy.client = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockPipelinePaginator:
        async def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"name": "pipeline-1"}, {"name": "pipeline-2"}]

    class MockExecutionPaginator:
        async def paginate(
            self, pipelineName: str
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if pipelineName == "pipeline-1":
                yield [
                    {"pipelineExecutionId": "execution-1"},
                    {"pipelineExecutionId": "execution-2"},
                ]
            else:
                yield [{"pipelineExecutionId": "execution-3"}]

    pipeline_paginator = MockPipelinePaginator()
    execution_paginator = MockExecutionPaginator()

    def get_paginator(operation: str, key: str) -> Any:
        if operation == "list_pipelines":
            return pipeline_paginator
        return execution_paginator

    mock_proxy.get_paginator = MagicMock(side_effect=get_paginator)

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    mock_response_one = MagicMock()
    mock_response_two = MagicMock()
    mock_inspector.inspect.side_effect = [
        [mock_response_one],
        [mock_response_two],
    ]

    # Act
    collected: list[list[dict[str, Any]]] = []
    async for page in exporter.get_paginated_resources(paginated_options):
        collected.append(page)

    # Assert
    assert collected == [[mock_response_one], [mock_response_two]]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_options.region, "codepipeline"
    )
    mock_proxy.get_paginator.assert_has_calls(
        [
            call("list_pipelines", "pipelines"),
            call("list_pipeline_executions", "pipelineExecutionSummaries"),
        ]
    )
    assert mock_inspector.inspect.call_count == 2

    mock_input.assert_has_calls(
        [
            call(
                items=[
                    {"pipelineExecutionId": "execution-1"},
                    {"pipelineExecutionId": "execution-2"},
                ],
                pipeline_name="pipeline-1",
            ),
            call(
                items=[{"pipelineExecutionId": "execution-3"}],
                pipeline_name="pipeline-2",
            ),
        ]
    )
    mock_inspector.inspect.assert_has_calls(
        [
            call(
                mock_input.return_value,
                paginated_options.include,
                extra_context={
                    "AccountId": paginated_options.account_id,
                    "Region": paginated_options.region,
                },
            ),
            call(
                mock_input.return_value,
                paginated_options.include,
                extra_context={
                    "AccountId": paginated_options.account_id,
                    "Region": paginated_options.region,
                },
            ),
        ]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelineExecutionActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_empty(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    paginated_options: PaginatedPipelineExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelinePipelineExecutionExporter(AsyncMock())
    mock_proxy = AsyncMock()
    mock_proxy.client = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockPipelinePaginator:
        async def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

    class MockExecutionPaginator:
        async def paginate(
            self, pipelineName: str
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"pipelineExecutionId": "execution-1"}]

    pipeline_paginator = MockPipelinePaginator()
    execution_paginator = MockExecutionPaginator()

    def get_paginator(operation: str, key: str) -> Any:
        if operation == "list_pipelines":
            return pipeline_paginator
        return execution_paginator

    mock_proxy.get_paginator = MagicMock(side_effect=get_paginator)

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    # Act
    collected: list[list[dict[str, Any]]] = []
    async for page in exporter.get_paginated_resources(paginated_options):
        collected.append(page)

    # Assert
    assert collected == []

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_options.region, "codepipeline"
    )
    mock_input.assert_not_called()
    mock_inspector.inspect.assert_not_called()
