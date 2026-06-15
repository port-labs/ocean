from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from aws.core.exporters.codepipeline.pipeline.exporter import PipelineExporter
from aws.core.exporters.codepipeline.pipeline.models import (
    SinglePipelineRequest,
    PaginatedPipelineRequest,
)

patch_prefix = "aws.core.exporters.codepipeline.pipeline.exporter"


@pytest.fixture
def single_options() -> SinglePipelineRequest:
    return SinglePipelineRequest(
        region="us-east-1",
        account_id="123456789012",
        pipeline_name="test-pipeline",
        include=[],
    )


@pytest.fixture
def paginated_options() -> PaginatedPipelineRequest:
    return PaginatedPipelineRequest(
        region="us-east-1",
        account_id="123456789012",
        include=[],
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelinePipelineActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    single_options: SinglePipelineRequest,
) -> None:
    # Arrange
    exporter = PipelineExporter(AsyncMock())
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
        items=[{"name": single_options.pipeline_name}],
        region=single_options.region,
        account_id=single_options.account_id,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value, single_options.include
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelinePipelineActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_empty_response(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    single_options: SinglePipelineRequest,
) -> None:
    # Arrange
    exporter = PipelineExporter(AsyncMock())
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
    mock_inspector.inspect.assert_called_once()
    mock_input.assert_called_once_with(
        items=[{"name": single_options.pipeline_name}],
        region=single_options.region,
        account_id=single_options.account_id,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value, single_options.include
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelinePipelineActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    paginated_options: PaginatedPipelineRequest,
) -> None:
    # Arrange
    exporter = PipelineExporter(AsyncMock())
    mock_proxy = AsyncMock()
    mock_client = AsyncMock()
    mock_proxy.client = mock_client
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
    mock_paginator = MagicMock()
    mock_proxy.get_paginator = MagicMock(return_value=mock_paginator)

    class MockPaginator:
        async def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"name": "pipeline-1"}, {"name": "pipeline-2"}]
            yield [{"name": "pipeline-3"}]

    paginator_instance = MockPaginator()
    mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    mock_response_one = MagicMock()
    mock_response_two = MagicMock()
    mock_response_three = MagicMock()
    mock_inspector.inspect.side_effect = [
        [mock_response_one, mock_response_two],
        [mock_response_three],
    ]

    # Act
    collected: list[list[dict[str, Any]]] = []
    async for page in exporter.get_paginated_resources(paginated_options):
        collected.append(page)

    # Assert
    assert collected == [[mock_response_one, mock_response_two], [mock_response_three]]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_options.region, "codepipeline"
    )
    mock_proxy.get_paginator.assert_called_once_with("list_pipelines", "pipelines")
    assert mock_inspector.inspect.call_count == 2

    mock_input.assert_has_calls(
        [
            call(
                items=[{"name": "pipeline-1"}, {"name": "pipeline-2"}],
                region=paginated_options.region,
                account_id=paginated_options.account_id,
            ),
            call(
                items=[{"name": "pipeline-3"}],
                region=paginated_options.region,
                account_id=paginated_options.account_id,
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
@patch(f"{patch_prefix}.CodePipelinePipelineActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_empty(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    paginated_options: PaginatedPipelineRequest,
) -> None:
    # Arrange
    exporter = PipelineExporter(AsyncMock())
    mock_proxy = AsyncMock()
    mock_client = AsyncMock()
    mock_proxy.client = mock_client
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
    mock_paginator = MagicMock()
    mock_proxy.get_paginator = MagicMock(return_value=mock_paginator)

    class MockPaginator:
        async def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

    paginator_instance = MockPaginator()
    mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    mock_response_one = MagicMock()
    mock_response_two = MagicMock()
    mock_response_three = MagicMock()
    mock_inspector.inspect.side_effect = [
        [mock_response_one, mock_response_two],
        [mock_response_three],
    ]

    # Act
    collected: list[list[dict[str, Any]]] = []
    async for page in exporter.get_paginated_resources(paginated_options):
        collected.append(page)

    # Assert
    assert collected == [[]]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_options.region, "codepipeline"
    )
    mock_proxy.get_paginator.assert_called_once_with("list_pipelines", "pipelines")
    mock_input.assert_not_called()
    mock_inspector.inspect.assert_not_called()
