from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, patch, MagicMock, call
import pytest

from aws.core.exporters.codepipeline.action_execution.exporter import (
    CodePipelineActionExecutionExporter,
)
from aws.core.exporters.codepipeline.action_execution.models import (
    SingleCodePipelineActionExecutionRequest,
    PaginatedCodePipelineActionExecutionRequest,
)

patch_prefix = "aws.core.exporters.codepipeline.action_execution.exporter"


@pytest.fixture
def single_options() -> SingleCodePipelineActionExecutionRequest:
    return SingleCodePipelineActionExecutionRequest(
        region="us-east-1",
        account_id="123456789012",
        pipeline_name="test-pipeline",
        action_execution_id="exec-id-123",
    )


@pytest.fixture
def paginated_options() -> PaginatedCodePipelineActionExecutionRequest:
    return PaginatedCodePipelineActionExecutionRequest(
        region="us-east-1", account_id="123456789012"
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelineActionExecutionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_success(
    mock_inspector_class: MagicMock,
    mock_proxy: MagicMock,
    mock_input: MagicMock,
    single_options: SingleCodePipelineActionExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelineActionExecutionExporter(AsyncMock())
    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    target_execution = {
        "actionExecutionId": single_options.action_execution_id,
        "actionName": "Source",
        "stageName": "Source",
        "status": "Succeeded",
    }
    other_execution = {
        "actionExecutionId": "other-exec-id",
        "actionName": "Build",
        "stageName": "Build",
        "status": "Succeeded",
    }
    mock_inspector.inspect.return_value = [other_execution, target_execution]

    # Act
    result = await exporter.get_resource(single_options)

    # Assert
    assert result == target_execution
    mock_proxy.assert_called_once_with(
        exporter.session, single_options.region, "codepipeline"
    )
    mock_input.assert_called_once_with(
        items=[{"name": single_options.pipeline_name}],
        region=single_options.region,
        account_id=single_options.account_id,
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
@patch(f"{patch_prefix}.CodePipelineActionExecutionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_not_found(
    mock_inspector_class: MagicMock,
    mock_proxy: MagicMock,
    mock_input: MagicMock,
    single_options: SingleCodePipelineActionExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelineActionExecutionExporter(AsyncMock())
    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector
    mock_inspector.inspect.return_value = []

    # Act
    result = await exporter.get_resource(single_options)

    # Assert
    assert result == {}
    mock_proxy.assert_called_once_with(
        exporter.session, single_options.region, "codepipeline"
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.CodePipelineActionExecutionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    paginated_options: PaginatedCodePipelineActionExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelineActionExecutionExporter(AsyncMock())
    mock_proxy = AsyncMock()
    mock_proxy.client = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockPaginator:
        async def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"name": "pipeline-1"}, {"name": "pipeline-2"}]
            yield [{"name": "pipeline-3"}]

    paginator_instance = MockPaginator()
    mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    exec_one = {"actionExecutionId": "exec-1", "stageName": "Source"}
    exec_two = {"actionExecutionId": "exec-2", "stageName": "Build"}
    exec_three = {"actionExecutionId": "exec-3", "stageName": "Deploy"}
    mock_inspector.inspect.side_effect = [
        [exec_one, exec_two],
        [exec_three],
    ]

    # Act
    collected: list[list[dict[str, Any]]] = []
    async for page in exporter.get_paginated_resources(paginated_options):
        collected.append(page)

    # Assert
    assert collected == [[exec_one, exec_two], [exec_three]]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_options.region, "codepipeline"
    )
    mock_proxy.get_paginator.assert_called_once_with("list_pipelines", "pipelines")
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
@patch(f"{patch_prefix}.CodePipelineActionExecutionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_empty(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    paginated_options: PaginatedCodePipelineActionExecutionRequest,
) -> None:
    # Arrange
    exporter = CodePipelineActionExecutionExporter(AsyncMock())
    mock_proxy = AsyncMock()
    mock_proxy.client = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockPaginator:
        async def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

    paginator_instance = MockPaginator()
    mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

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
