from typing import AsyncGenerator

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aws.core.exporters.codebuild.build_run.exporter import CodeBuildBuildRunExporter
from aws.core.exporters.codebuild.build_run.models import (
    SingleBuildRunRequest,
    PaginatedBuildRunRequest,
)


@pytest.fixture
def single_build_run_options() -> SingleBuildRunRequest:
    return SingleBuildRunRequest(
        region="us-east-1",
        account_id="123456789012",
        build_id="test-project:abcdef12-3456-7890-abcd-ef1234567890",
        include=[],
    )


@pytest.fixture
def paginated_options() -> PaginatedBuildRunRequest:
    return PaginatedBuildRunRequest(
        region="us-east-1", account_id="123456789012", include=[]
    )


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.build_run.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.build_run.exporter.ResourceInspector")
async def test_get_resource(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    single_build_run_options: SingleBuildRunRequest,
) -> None:
    # Arrange
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance

    expected_result = MagicMock()
    mock_inspector_instance.inspect.return_value = [expected_result]

    # Act
    exporter = CodeBuildBuildRunExporter(mock_session)
    result = await exporter.get_resource(single_build_run_options)

    # Assert
    assert result == expected_result
    mock_proxy_class.assert_called_once_with(mock_session, single_build_run_options.region, "codebuild")
    mock_inspector_instance.inspect.assert_called_once_with([single_build_run_options.build_id],
                                                            single_build_run_options.include)


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.build_run.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.build_run.exporter.ResourceInspector")
async def test_get_resource_empty_response(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    single_build_run_options: SingleBuildRunRequest,
) -> None:
    # Arrange
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance
    mock_inspector_instance.inspect.return_value = []

    # Act
    exporter = CodeBuildBuildRunExporter(mock_session)
    result = await exporter.get_resource(single_build_run_options)

    # Assert
    assert result == {}


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.build_run.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.build_run.exporter.ResourceInspector")
async def test_get_paginated_resources(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    paginated_options: PaginatedBuildRunRequest,
) -> None:
    # Arrange
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_paginator = MagicMock()
    mock_proxy_instance.get_paginator = MagicMock(return_value=mock_paginator)

    async def mock_paginate_generator(**kwargs) -> AsyncGenerator[list[str], None]:
        yield ["project:build1", "project:build2"]
        yield ["project:build3"]
        yield []

    mock_paginator.paginate = MagicMock(side_effect=mock_paginate_generator)

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance

    inspector_result_1 = [MagicMock(), MagicMock()]
    inspector_result_2 = [MagicMock()]

    mock_inspector_instance.inspect.side_effect = [
        inspector_result_1,
        inspector_result_2,
    ]

    # Act
    exporter = CodeBuildBuildRunExporter(mock_session)
    results = []
    async for batch in exporter.get_paginated_resources(paginated_options):
        results.append(batch)

    # Assert
    assert len(results) == 3
    assert len(results[0]) == 2
    assert len(results[1]) == 1
    assert len(results[2]) == 0

    assert results[0][0] == inspector_result_1[0]
    assert results[0][1] == inspector_result_1[1]
    assert results[1][0] == inspector_result_2[0]

    mock_proxy_instance.get_paginator.assert_called_once_with("list_builds", "ids")
    assert mock_inspector_instance.inspect.call_count == 2


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.build_run.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.build_run.exporter.ResourceInspector")
async def test_get_paginated_resources_empty_page(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    paginated_options: PaginatedBuildRunRequest,
) -> None:
    # Arrange
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_paginator = MagicMock()
    mock_proxy_instance.get_paginator = MagicMock(return_value=mock_paginator)

    async def mock_paginate_generator(**kwargs) -> AsyncGenerator[list[str], None]:
        yield []
        yield []

    mock_paginator.paginate = MagicMock(side_effect=mock_paginate_generator)

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance

    # Act
    exporter = CodeBuildBuildRunExporter(mock_session)
    results = []
    async for batch in exporter.get_paginated_resources(paginated_options):
        results.append(batch)

    # Assert
    assert len(results) == 2
    assert all(len(batch) == 0 for batch in results)
    mock_inspector_instance.inspect.assert_not_called()
