from typing import AsyncGenerator

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aws.core.exporters.codebuild.project.exporter import CodeBuildProjectExporter
from aws.core.exporters.codebuild.project.models import (
    SingleCodeBuildProjectRequest,
    PaginatedCodeBuildProjectRequest,
)


@pytest.fixture
def single_project_options() -> SingleCodeBuildProjectRequest:
    return SingleCodeBuildProjectRequest(
        region="us-east-1",
        account_id="123456789012",
        project_name="test-project",
        include=[],
    )


@pytest.fixture
def paginated_options() -> PaginatedCodeBuildProjectRequest:
    return PaginatedCodeBuildProjectRequest(
        region="us-east-1", account_id="123456789012", include=[]
    )


@pytest.mark.asyncio
async def test_codebuild_project_exporter_service_name() -> None:
    exporter = CodeBuildProjectExporter(AsyncMock())
    assert exporter._service_name == "codebuild"


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.project.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.project.exporter.ResourceInspector")
async def test_get_resource(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    single_project_options: SingleCodeBuildProjectRequest,
) -> None:
    # Setup mocks
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance

    expected_result = {
        "name": "test-project",
        "arn": "arn:aws:codebuild:us-east-1:123456789012:project/test-project",
        "description": "Test project",
    }
    mock_inspector_instance.inspect.return_value = [expected_result]

    # Test
    exporter = CodeBuildProjectExporter(mock_session)
    result = await exporter.get_resource(single_project_options)

    # Assertions
    assert result == expected_result
    mock_proxy_class.assert_called_once_with(mock_session, "us-east-1", "codebuild")
    mock_inspector_instance.inspect.assert_called_once_with(
        [{"name": "test-project"}], []
    )


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.project.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.project.exporter.ResourceInspector")
async def test_get_resource_empty_response(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    single_project_options: SingleCodeBuildProjectRequest,
) -> None:
    # Setup mocks
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance
    mock_inspector_instance.inspect.return_value = []

    # Test
    exporter = CodeBuildProjectExporter(mock_session)
    result = await exporter.get_resource(single_project_options)

    # Assertions
    assert result == {}


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.project.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.project.exporter.ResourceInspector")
async def test_get_paginated_resources(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    paginated_options: PaginatedCodeBuildProjectRequest,
) -> None:
    # Setup mocks
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_paginator = MagicMock()
    mock_proxy_instance.get_paginator = MagicMock(return_value=mock_paginator)

    async def mock_paginate_generator() -> AsyncGenerator[list[str], None]:
        yield ["project1", "project2"]
        yield ["project3"]
        yield []

    mock_paginator.paginate = MagicMock(side_effect=mock_paginate_generator)

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance

    # Mock inspector responses
    inspector_result_1 = [
        {
            "name": "project1",
            "arn": "arn:aws:codebuild:us-east-1:123456789012:project/project1",
        },
        {
            "name": "project2",
            "arn": "arn:aws:codebuild:us-east-1:123456789012:project/project2",
        },
    ]
    inspector_result_2 = [
        {
            "name": "project3",
            "arn": "arn:aws:codebuild:us-east-1:123456789012:project/project3",
        }
    ]

    mock_inspector_instance.inspect.side_effect = [
        inspector_result_1,
        inspector_result_2,
    ]

    # Test
    exporter = CodeBuildProjectExporter(mock_session)
    results = []
    async for batch in exporter.get_paginated_resources(paginated_options):
        results.append(batch)

    # Assertions
    assert len(results) == 3  # Two batches with data, one empty
    assert len(results[0]) == 2  # First batch
    assert len(results[1]) == 1  # Second batch
    assert len(results[2]) == 0  # Empty batch

    assert results[0][0]["name"] == "project1"
    assert results[0][1]["name"] == "project2"
    assert results[1][0]["name"] == "project3"

    # Verify paginator was set up correctly
    mock_proxy_instance.get_paginator.assert_called_once_with(
        "list_projects", "projects"
    )

    # Verify inspector was called for non-empty batches
    assert mock_inspector_instance.inspect.call_count == 2


@pytest.mark.asyncio
@patch("aws.core.exporters.codebuild.project.exporter.AioBaseClientProxy")
@patch("aws.core.exporters.codebuild.project.exporter.ResourceInspector")
async def test_get_paginated_resources_empty_page(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    paginated_options: PaginatedCodeBuildProjectRequest,
) -> None:
    # Setup mocks
    mock_session = AsyncMock()
    mock_proxy_instance = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy_instance

    mock_paginator = MagicMock()
    mock_proxy_instance.get_paginator = MagicMock(return_value=mock_paginator)

    async def mock_paginate_generator() -> AsyncGenerator[list[str], None]:
        yield []
        yield []

    mock_paginator.paginate = MagicMock(side_effect=mock_paginate_generator)

    mock_inspector_instance = AsyncMock()
    mock_inspector_class.return_value = mock_inspector_instance

    # Test
    exporter = CodeBuildProjectExporter(mock_session)
    results = []
    async for batch in exporter.get_paginated_resources(paginated_options):
        results.append(batch)

    # Assertions
    assert len(results) == 2
    assert all(len(batch) == 0 for batch in results)

    # Verify inspector was not called for empty batches
    mock_inspector_instance.inspect.assert_not_called()
